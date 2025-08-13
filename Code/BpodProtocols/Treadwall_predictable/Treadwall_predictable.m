function Treadwall_predictable

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

location = questdlg('Where do you perform your experiments?',...
    'Locations',...
    'BN','ISR','ISR');

params_file = fullfile([BpodSystem.Path.ProtocolFolder '\treadwall_scrambled_parameters_', location, '.m']);
run(params_file)

fprintf('Parameters loaded for: %s \n', location);

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;

    S.GUI.ITIDur = ITIDur; %in seconds
    S.GUI.ScalingFactor = 1;

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Trials ------------------------------------------------------
% one trial will be defined as one lap on the tradmill
% maximum 50 laps per session
S.GUI.MaxTrialNumber = 50;

%% ---------- Arduino Synchronizer ----------------------------------------
arduino = serialport('COM7', 115385);

% Send initial value to Arduino
scalingValue = S.GUI.ScalingFactor;
writeline(arduino, strcat(num2str(scalingValue), '\n'));
lastScalingFactor = scalingValue;

%% ---------- Rotary Encoder Module ---------------------------------------
R = RotaryEncoderModule('COM8'); %check which COM is paired with rotary encoder module
% R.thresholds = [180,0];
% R.sendThresholdEvents = 'On';
% R.enableThresholds([1,1,1])
% R.streamUI()

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Master';

% Calculate 16bit value for Voltage Output
% for i = 1:length(waveforms)
%     waveforms{i} = (waveforms{i}/5)*65535;
% end

% Waveforms for offset distances
lengthWave = 1800*W.SamplingRate; %maximum length of session
for i = 1:length(waveforms)
    W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
end

%% ---------- Analog Input Module ----------------------------------------
A = BpodAnalogIn('COM10'); %check which COM is paired with analog input module

A.SamplingRate = 100;%in kHz
A.InputRange = {'0V:10V', '0V:10V', '0V:10V', '0V:10V', '0V:10V', '0V:10V', '0V:10V', '0V:10V'};
A.nActiveChannels = 2;
A.Thresholds(1) = 1.5;
A.ResetVoltages(1) = 3;
A.SMeventsEnabled(1) = 1;

A.startReportingEvents()
%A.scope()
%% ---------- Setup Camera ------------------------------------------------
% disp('Starting Python video acquisition script...');
% 
% pythonExe = 'C:\Users\TomBombadil\anaconda3\python.exe';
% pyenv('Version', pythonExe);
% 
% scriptPath = "C:\Users\TomBombadil\Documents\GitHub\Treadwall\Code\Camera\VideoAquisition.py";
% 
% % Run in background
% command = sprintf('"%s" "%s" "%s" "%s" "%s" &', pythonExe, scriptPath, session_dir, S.GUI.SubjectID, S.GUI.SessionID);
% system(command);

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Synching with WaveSurfer ------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'WaitForWaveSurfer', ...
    'Timer',0,...
    'StateChangeConditions', {'BNC1High', 'exit'},...
    'OutputActions', {'WavePlayer1', ['!' 3 0 0]});
SendStateMachine(sma);
disp('Waiting for Wavesurfer...');
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) % If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
    SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Loop: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS')]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % Get current Scaling value
    scalingValue = S.GUI.ScalingFactor;
    % If changed, update Arduino
    if scalingValue ~= lastScalingFactor
        writeline(arduino, strcat(num2str(scalingValue), '\n'));
        lastScalingFactor = scalingValue;
        fprintf('Updated Arduino with new ScalingFactor: %.1f \n', scalingValue);
    end

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description
    sma = SetGlobalTimer(sma, 'TimerID', 1, 'Duration', 1800);

    if currentTrial == 1 %first trial
        sma = AddState(sma, 'Name', 'StartBuffer', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'quarter1'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'quarter1',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter2', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 5 5 255 255]});

        sma = AddState(sma, 'Name', 'quarter2',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter3', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 3 3 255 255]});

        sma = AddState(sma, 'Name', 'quarter3',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter4', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 4 4 255 255]});

        % exit trial after completeing last quarter
        sma = AddState(sma, 'Name', 'quarter4',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','exit', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 2 2 255 255]});

        sma = AddState(sma, 'Name', 'EndBuffer',...
            'Timer', 10,...
            'StateChangeConditions', {'Tup', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 0,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});

    else
        sma = AddState(sma, 'Name', 'quarter1',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter2', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 5 5 255 255]});

        sma = AddState(sma, 'Name', 'quarter2',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter3', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 3 3 255 255]});

        sma = AddState(sma, 'Name', 'quarter3',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','quarter4', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 4 4 255 255]});

        % exit trial after completeing last quarter
        sma = AddState(sma, 'Name', 'quarter4',...
            'Timer',0,...
            'StateChange Conditions', {'AnalogIn1_1','exit', 'GlobalTimer1_End', 'EndBuffer'},...
            'OutputActions', {'WavePlayer1', ['>' 2 2 255 255]});

        sma = AddState(sma, 'Name', 'EndBuffer',...
            'Timer', 10,...
            'StateChangeConditions', {'Tup', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 0,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});
    end

    % run state machine
    SendStateMachine(sma);
    RawEvents = RunStateMachine;

    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        BpodSystem.Data.TrialSettings(currentTrial) = S;
        BpodSystem.Data.Loop(currentTrial) = currentTrial;
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        %SaveProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end

clear arduino
disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end