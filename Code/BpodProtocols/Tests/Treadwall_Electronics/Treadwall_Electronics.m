function Treadwall_Electronics
% this script can be used to test the proper functioning of the mover and synchronizer
% wavesurfer is not needed for testing
% trial and ITI times are kept short
% trials iterate from wide to narrow distance

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = 'C:\Users\TomBombadil\Desktop\Animals\Cohort00_Test'; %Tests should always be saved in this folder

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);
    
    % Timings
    S.GUI.ITIDur = 5; %in seconds
    S.GUI.stimDur = 5; %in seconds

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Create Triallist and load Trials ----------------------------
% read triallist
trialList_Info =  dir([BpodSystem.Path.ProtocolFolder '\triallist_testing.csv']);
if isempty(trialList_Info)
    [~,triallist_dir] = uigetfile(fullfile(start_path,'*.csv'));
else
    triallist_dir = fullfile(trialList_Info.folder, trialList_Info.name);
end

triallist = readtable(triallist_dir);
triallist = triallist.type;
S.GUI.MaxTrialNumber = numel(triallist);

%% ---------- Rotary Encoder Module ---------------------------------------
R = RotaryEncoderModule('COM8'); %check which COM is paired with rotary encoder module
R.streamUI();

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

% Waveforms for offset distances
lengthWave = S.GUI.stimDur*W.SamplingRate;
waveforms = {1.2, 1.84, 2.47, 3.1, 3.73, 4.37,...
    1.33, 1.91, 2.55, 3.14, 3.78, 4.36, 5};
for i = 1:length(waveforms)
    W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
end

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' triallist{currentTrial}]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % read output action
    stimOutput = GetStimOutput(triallist{currentTrial});

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description

    if currentTrial == 1 %first trial
        sma = AddState(sma, 'Name', 'StartBuffer', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'stimulus'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'iti'},...
            'OutputActions', {'WavePlayer1', stimOutput});

        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});
    else
        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'iti'},...
            'OutputActions', {'WavePlayer1', stimOutput});

        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});
    end

    % run state machine
    SendStateMachine(sma);
    RunStateMachine;
    if BpodSystem.Status.BeingUsed == 0; return; end
end

disp('Loop end');
disp('Close Stream. Stop Bpod');
end