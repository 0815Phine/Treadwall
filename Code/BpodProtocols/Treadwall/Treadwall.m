function Treadwall

global BpodSystem

%% ---------- Define task parameters --------------------------------------
% initialize parameters
S = BpodSystem.ProtocolSettings;

%params_file = '';
%run(params_file)
start_path = 'C:\Users\TomBombadil\Desktop\Animals'; %check on experiment computer
%start_path = uigetdir(start_path, 'Select Cohort');

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectName = BpodSystem.GUIData.SubjectName;
    %S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    
    % Timings
    S.GUI.ITIDur = 5; %in seconds
    S.GUI.stimDur = 10; %in seconds

    S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);

% define and randomize trials
trialList_Info = dir([start_path '\Cohort00_Test\#Test\01\triallist.csv']);
%trialList_Info = dir([S.GUI.ExpInfoPath '\' S.GUI.SubjectNme '\' S.GUI.SessionID '\triallist.csv']);
if isempty(trialList_Info)
    [~,triallist_dir] = uigetfile(fullfile(start_path,'*.csv'));
else
    triallist_dir = fullfile(trialList_Info.folder, trialList_Info.name);
end

triallist = readtable(triallist_dir);
triallist = triallist.type;
S.GUI.MaxTrialNumber = numel(triallist);

%% ---------- Analog Output Module ----------------------------------------
% if (isfield(BpodSystem.ModuleUSB, 'WavePlayer1'))
%     W = BpodSystem.ModuleUSB.WavePlayer1;
% else
%     error('Error: To run this protocol, you must first pair the WavePlayer1 module with its USB port on the Bpod console.')
% end

W = BpodWavePlayer('COM8');

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

lengthWave = S.GUI.stimDur*W.SamplingRate;
W.loadWaveform(1, 3*ones(1,lengthWave));
W.loadWaveform(2, 4*ones(1,lengthWave));
W.loadWaveform(3, 5*ones(1,lengthWave));

%W.LoopMode = 'on';
%W.LoopDuration = S.GUI.ITIDur;
%W.BpodEvents = 'off';

%LoadSerialMessages('WavePlayer1', {['P' 0]});

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
            stimOutput = ['P' 3 0];
        case 'L'
            stimOutput = ['P' 3 1];
        case 'R'
            stimOutput = ['P' 3 2];
    end

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description
    
    if currentTrial == numel(triallist) %last trial
        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'stimulus'},...
            'OutputActions', {});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', stimOutput});

        sma = AddState(sma, 'Name', 'EndBuffer', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {});
    else
        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'stimulus'},...
            'OutputActions', {});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'WavePlayer1', stimOutput});
    end

    SendStateMachine(sma);
    RawEvents = RunStateMachine;
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end