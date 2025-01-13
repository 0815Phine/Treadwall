function Treadwall_Tuning

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct();

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    
    % Timings
    S.GUI.ITIDur = 8; %in seconds
    S.GUI.stimDur = 30; %in seconds

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);

% define trials (from previously created randomized list)
trialList_Info = dir('C:\Users\TomBombadil\Documents\GitHub\Treadwall\Code\Arduino\Distance_Sensor\TuningCurve\triallist.csv');
if isempty(trialList_Info)
    %[~,triallist_dir] = uigetfile(fullfile(start_path,'*.csv'));
    error('no triallist found')
else
    triallist_dir = fullfile(trialList_Info.folder, trialList_Info.name);
end

triallist = readtable(triallist_dir);
triallist = triallist.type;
S.GUI.MaxTrialNumber = numel(triallist);

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

lengthWave = S.GUI.stimDur*W.SamplingRate;
waveforms = {0.4, 0.8, 1.2, 1.6, 2, 2.4, 2.8, 3.2, 3.6, 4, 4.5, 5};
for i = 1:length(waveforms)
    W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
end

%% ---------- Synching with Python ----------------------------------------
% Define the tuning file path with current date
date_str = datestr(now, 'yyyy-mm-dd');
tuning_folder_path = fullfile(start_path,'\Tuning\', date_str);
if ~exist(tuning_folder_path, 'dir')
    mkdir(tuning_folder_path);
end

stopFile = fullfile(tuning_folder_path, 'stop.txt'); 
if exist(stopFile, 'file'), delete(stopFile); end % Ensure no residual stop signal

% Define the path to the Python executable and the Python script
pythonExe = 'C:\Users\TomBombadil\anaconda3\python.exe'; % Path to Python interpreter
pythonScript = 'C:\Users\TomBombadil\Documents\GitHub\Treadwall\Code\Arduino\Distance_Sensor\TuningCurve\log_data.py';
logFilePath = fullfile(tuning_folder_path, 'tuning.csv');
cmd = sprintf('%s %s "%s" &', pythonExe, pythonScript, logFilePath);
system(cmd);

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    % disp(' ');
    % disp('- - - - - - - - - - - - - - - ');
    % disp(['Trial: ' num2str(trial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' typeList{trial}]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % read output action
    stimOutput = GetStimOutput(triallist{currentTrial});

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

    % Save data if returned
    if ~isempty(fieldnames(RawEvents))
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        %SaveProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end

disp('Loop end');

%% ---------- Stop Python -------------------------------------------------
% Signal file to stop Python logging (to be created at the end)
stopSignalFile = fullfile(tuning_folder_path, 'stop.txt');
% Create stop.txt at the end of the main loop
if BpodSystem.Status.BeingUsed == 0 || currentTrial == S.GUI.MaxTrialNumber
    fid = fopen(stopSignalFile, 'w');
    fclose(fid);
end
end