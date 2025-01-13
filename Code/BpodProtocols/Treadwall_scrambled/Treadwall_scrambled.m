function Treadwall_scrambled

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals';

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

params_file = fullfile([BpodSystem.Path.ProtocolFolder '\treadwall_parameters.m']);
run(params_file)

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    
    % Timings
    S.GUI.ITIDur = ITIDur; %in seconds
    S.GUI.stimDur = stimDur; %in seconds

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
% disp('Please do not yet start Wavesurfer...');
% pause(1);

%% ---------- Create Triallist and load Trials ----------------------------
% create triallist (adjust function according to trials needed
create_triallist_all(start_path, S.GUI.SubjectID, S.GUI.SessionID); % all distances and all offsets

% read triallist
trialList_Info = dir([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID '\triallist.csv']);
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

W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

lengthWave = S.GUI.stimDur*W.SamplingRate;
W.loadWaveform(1, 0.4*ones(1,lengthWave));
W.loadWaveform(2, 0.8*ones(1,lengthWave));
W.loadWaveform(3, 1.2*ones(1,lengthWave));
W.loadWaveform(4, 1.6*ones(1,lengthWave));
W.loadWaveform(5, 2*ones(1,lengthWave));
W.loadWaveform(6, 2.4*ones(1,lengthWave));
W.loadWaveform(7, 2.8*ones(1,lengthWave));
W.loadWaveform(8, 3.2*ones(1,lengthWave));
W.loadWaveform(9, 3.6*ones(1,lengthWave));
W.loadWaveform(10, 4*ones(1,lengthWave));
W.loadWaveform(11, 4.5*ones(1,lengthWave));
W.loadWaveform(12, 5*ones(1,lengthWave));

%W.LoopMode = 'on';
%W.LoopDuration = S.GUI.ITIDur;
%W.BpodEvents = 'off';

%LoadSerialMessages('WavePlayer1', {['P' 0]});

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Synching with WaveSurfer ------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'WaitForWaveSurfer', ...
    'Timer',0,...
    'StateChangeConditions', {'BNC1High', 'exit'},...
    'OutputActions', {});
SendStateMachine(sma);
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) % If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
    SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    % disp(' ');
    % disp('- - - - - - - - - - - - - - - ');
    % disp(['Trial: ' num2str(trial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' typeList{trial}]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % read output action
    switch triallist{currentTrial}
        case 'C45'
            stimOutput = ['P' 3 0];
        case 'C39'
            stimOutput = ['P' 3 1];
        case 'C33'
            stimOutput = ['P' 3 2];
        case 'C27'
            stimOutput = ['P' 3 3];
        case 'L45'
            stimOutput = ['P' 3 4];
        case 'L39'
            stimOutput = ['P' 3 5];
        case 'L33'
            stimOutput = ['P' 3 6];
        case 'L27'
            stimOutput = ['P' 3 7];
        case 'R45'
            stimOutput = ['P' 3 8];
        case 'R39'
            stimOutput = ['P' 3 9];
        case 'R33'
            stimOutput = ['P' 3 10];
        case 'R27'
            stimOutput = ['P' 3 11];
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

    % run state machine
    SendStateMachine(sma);
    RawEvents = RunStateMachine;
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        SaveProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end

disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end