function Treadwall_predictable

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;

    %Speed scaling
    S.GUI.PulseDuration = 0.0025 ;%PulseDuration: default one-on-one scaling, pulse width in seconds

    % set thresholds for rotary encoder here

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

% disp('Please do not yet start Wavesurfer...');
% pause(1);

%% ---------- Trials ------------------------------------------------------
% one trial will be defined as one lap on the tradmill

% test for scalinmg of stepper speed
% PulseDuration = [0.0005, 0.001, 0.0015, 0.002, 0.0025, 0.003, 0.0035, 0.004, 0.0045, 0.005];
% S.GUI.MaxTrialNumber = numel(PulseDuration);
S.GUI.MaxTrialNumber = 30; % walks 30 times complete treadmill

%% ---------- Rotary Encoder Module ---------------------------------------
R = RotaryEncoderModule('COM8'); %check which COM is paired with rotary encoder module
R.thresholds = [-180, -90, 90, 180];
R.sendThresholdEvents = 'On';
R.enableThresholds(1,1,1,1)

R.startUSBStream()
data = R.readUSBStream();
%R.streamUI()

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';
%W.TriggerProfileEnable = 'On'; % for simultaneous triggering of different channels

% %for setting tic analog position control
% lengthWave = 30*W.SamplingRate;
% waveforms = {0, 2.5, 5};
% for i = 1:length(waveforms)
%     W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
% end

% set wall trigger profiles for speed and wall diameter

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Synching with WaveSurfer ------------------------------------
% sma = NewStateMachine();
% sma = AddState(sma, 'Name', 'WaitForWaveSurfer', ...
%     'Timer',0,...
%     'StateChangeConditions', {'BNC1High', 'exit'},...
%     'OutputActions', {});
% SendStateMachine(sma);
% RawEvents = RunStateMachine;
% 
% if ~isempty(fieldnames(RawEvents)) % If trial data was returned
%     BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
%     SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
% end
% 
% disp('Synced with Wavesurfer.');
% %R.startLogging() %'L'

%% option with Behavior Port -> this doesn't work (invalid op code received)
% sma = NewStateMachine(); %Assemble new state machine description
% 
% sma = AddState(sma, 'Name', 'LightPort1', ...
%     'Timer', 60,...
%     'StateChangeConditions', {'Tup', 'exit'},...
%     'OutputActions', {'PWM1', 255});
% 
% SendStateMachine(sma);
% RunStateMachine;

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    % disp(' ');
    % disp('- - - - - - - - - - - - - - - ');
    % disp(['Trial: ' num2str(trial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' typeList{trial}]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description
    sma = SetGlobalTimer(sma, 'TimerID', 1, 'Duration', 1800);

    %R.zeroPosition() % set position of rotary encoder to 0 or 'Z'
    % reset rotary encoder
    sma = AddState(sma, 'Name', 'ResetEncoder', ...
        'Timer', 0,...
        'StateChangeConditions', {'Tup', 'center45_1'},...
        'OutputActions', {'RotaryEncoder1', 'ZE', 'GlobalTimerTrig', 1});

    % next move walls in at specific position
    sma = AddState(sma, 'Name', 'center45_1', ...
        'Timer', 0,...
        'StateChangeConditions', {'RotaryEncoder1_4', 'center45_2', 'RotaryEncoder1_1', 'center45_2'},...
        'OutputActions', {'WavePlayer1', ['!' 1 18 130], 'RotaryEncoder1', 'ZE'});

    sma = AddState(sma, 'Name', 'center45_2', ...
        'Timer', 0,...
        'StateChangeConditions', {'RotaryEncoder1_3', 'center39_1', 'RotaryEncoder1_2', 'center27_1'},...
        'OutputActions', {'WavePlayer1', ['!' 1 18 130], 'RotaryEncoder1', 'ZE'});

    sma = AddState(sma, 'Name', 'center39', ...
        'Timer', 0,...
        'StateChangeConditions', {'RotaryEncoder1_1', 'center33'},...
        'OutputActions', {'WavePlayer1', ['!' 1  34 155], 'RotaryEncoder1', 'ZE'});

    sma = AddState(sma, 'Name', 'center33', ...
        'Timer', 0,...
        'StateChangeConditions', {'RotaryEncoder1_1', 'center27'},...
        'OutputActions', {'WavePlayer1', ['!' 1 181 194], 'RotaryEncoder1', 'ZE'});

    sma = AddState(sma, 'Name', 'center27', ...
        'Timer', 0,...
        'StateChangeConditions', {'RotaryEncoder1_1', 'center45', 'GlobalTimer1_End', 'exit'},...
        'OutputActions', {'WavePlayer1', ['!' 1 205 210], 'RotaryEncoder1', 'ZE'});

    % exit trial at complete loop of treadmill




    % sma = AddState(sma, 'Name', 'Pulse', ...
    %     'Timer', PulseDuration(currentTrial),...
    %     'StateChangeConditions', {'Tup', 'Wait'},...
    %     'OutputActions', {'BNC1', 1});
    % 
    % sma = AddState(sma, 'Name', 'Wait', ...
    %     'Timer', 10,...
    %     'StateChangeConditions', {'Tup', 'exit'},...
    %     'OutputActions', {});

    % sma = AddState(sma, 'Name', 'stimulus_neu', ...
    %     'Timer', 30,...
    %     'StateChangeConditions', {'Tup', 'stimulus_max'},...
    %     'OutputActions', {'WavePlayer1', ['!' 3 0 128]});
    % 
    % sma = AddState(sma, 'Name', 'stimulus_max', ...
    %     'Timer', 30,...
    %     'StateChangeConditions', {'Tup', 'stimulus_min'},...
    %     'OutputActions', {'WavePlayer1', ['!' 3 255 255]});
    % 
    % sma = AddState(sma, 'Name', 'stimulus_min', ...
    %     'Timer', 30,...
    %     'StateChangeConditions', {'Tup', 'exit'},...
    %     'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

    % run state machine
    SendStateMachine(sma);
    RawEvents = RunStateMachine;

    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        %SaveProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end

%R.stopLogging()
%rotary_data = R.getLoggedData();

disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end