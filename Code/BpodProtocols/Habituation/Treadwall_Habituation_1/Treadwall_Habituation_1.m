function Treadwall_Habituation_1

%% ADD SCALING ADD CAMERA STOP
global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

params_file = fullfile([BpodSystem.Path.ProtocolFolder '\treadwall_habituation1_parameters.m']);
run(params_file)

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);
    
    % Timings
    S.GUI.stimDur = stimDur; %in seconds

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Rotary Encoder Module ---------------------------------------
R = RotaryEncoderModule('COM8'); %check which COM is paired with rotary encoder module
%R.streamUI()

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

% Waveforms for offset distances
% the following waveforms are calibrated for my guiding plate, they might have to be adapted
lengthWave = S.GUI.stimDur*W.SamplingRate;
waveforms = {0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5};
for i = 1:length(waveforms)
    W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
end

%% ---------- Setup Camera ------------------------------------------------
disp('Starting Python video acquisition script...');

pythonExe = 'C:\Users\TomBombadil\anaconda3\python.exe';
pyenv('Version', pythonExe);

scriptPath = "C:\Users\TomBombadil\Documents\GitHub\Treadwall\Code\Camera\VideoAquisition.py";

% Run in background
command = sprintf('"%s" "%s" "%s" "%s" "%s" &', pythonExe, scriptPath, session_dir, S.GUI.SubjectID, S.GUI.SessionID);
system(command);

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
disp('Waiting for Wavesurfer...');
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) % If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
    SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:floor(length(waveforms)/2)
    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS')]);

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description

    if currentTrial == 1 %first trial
        sma = AddState(sma, 'Name', 'Baseline', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'stimulus'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'WavePlayer1', ['>' currentTrial-1 currentTrial-1 255 255]});

    else
        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'WavePlayer1', ['>' currentTrial-1 currentTrial-1 255 255]});
    end

    % run state machine
    SendStateMachine(sma);
    RawEvents = RunStateMachine();
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        BpodSystem.Data.TrialSettings(currentTrial) = S;
        %BpodSystem.Data.TrialTypes(currentTrial) = triallist(currentTrial);
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        %SaveProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end

disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end