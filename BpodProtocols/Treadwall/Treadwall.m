function Treadwall

global BpodSystem

%% ---------- Define task parameters --------------------------------------
% initialize parameters
S = BpodSystem.ProtocolSettings;

%params_file = '';
%run(params_file)
start_path = 'Z:\Animals\Cohort00_Test'; %check on experiment computer

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectID;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    
    % Timings
    S.GUI.ITIDur = 12; %in seconds
    S.GUI.stimDur = 60; %in seconds

    S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);

% define and randomize trials
% trialList_Info = dir([start_path '\' '#Test' '\' '01' '\' 'triallist' '.csv'])
trialList_Info = dir([S.GUI.ExpInfoPath '\' S.GUI.SubjectID '\' S.GUI.SessionID '\triallist.csv']);
if isempty(trialList_Info)
    [~,triallist_dir] = uigetfile(fullfile(start_path,'*.csv'));
else
    triallist_dir = fullfile(trialList_Info.folder, trialList_Info.name);
end

triallist = readtable(triallist_dir);
S.GUI.MaxTrialNumber = numel(triallist);

%% ---------- Analog Output Module ----------------------------------------
BpodSystem.assertModule('WavePlayer1', {'WavePlayer1'});
W = BpodWavePlayer('');

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

oneVoltage = 1 * ones(1, W.SamplingRate); %1V
loadWaveform(1, oneVoltage);

W.LoopMode = 'on';
W.LoopDuration = S.GUI.ITIDur;
W.BpodEvents = 'off';

LoadSerialMessages('WavePlayer1', {['P' 0]});

%% ---------- Restart Timer and start Rotary Encoder Stream ---------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % read output action
    switch triallist{currentTrial}
        case 'C'
            fixedVoltage = 5;
        case 'L'
            fixedVoltage = 4;
        case 'R'
            fixedVoltage = 3;
    end

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description

    sma = AddState(sma, 'Name', 'iti', ...
        'Timer', S.GUI.ITIDur,...
        'StateChangeConditions', {'Tup', 'stimulus'},...
        'OutputActions', {'WavePlayer1', 1});

    sma = AddState(sma, 'Name', 'stimulus', ...
        'Timer', S.GUI.stimDur,...
        'StateChangeConditions', {'Tup', 'iti'},...
        'OutputActions', {});

    SendStateMachine(sma);
    RawEvents = RunStateMachine;
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end