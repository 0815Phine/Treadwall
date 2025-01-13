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

    % set thresholds for rotary encoder here

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

% disp('Please do not yet start Wavesurfer...');
% pause(1);

%% ----------

% one trial will be defined as one lap on the tradmill

%% ---------- Rotary Encoder Module ---------------------------------------

R = RotaryEncoderModule('COM10'); %check which COM is paired with rotary encoder module
R.moduleOutputStream = 'On'; %'0'
%R.streamUI()

%% ---------- Analog Output Module ----------------------------------------
W = BpodWavePlayer('COM3'); %check which COM is paired with analog output module

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';
W.TriggerProfileEnable = 'On'; % for simultaneous triggering of different channels

% set wall trigger profiles for speed and wall diameter

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
R.zeroPosition() % set position of rotary encoder to 0 or 'Z'
R.startLogging() %'L'

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:10
    % disp(' ');
    % disp('- - - - - - - - - - - - - - - ');
    % disp(['Trial: ' num2str(trial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' typeList{trial}]);

    S = BpodParameterGUI('sync', S); %Sync parameters with BpodParameterGUI plugin

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description

    sma = AddState(sma, 'Name', 'TrialStart', ...
        'Timer', 0,...
        'StateChangeConditions', {'Tup', 'ZeroEncoder'},...
        'OutputActions', {'RotaryEncoder1', ['#' 0]}); % marks a trial start timestamp in the rotary encoder data stream (for sync)

    % next move walls in at specific position
    %exit trial at complete loop of treadmill

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

R.stopLogging()
rotary_data = R.getLoggedData();

disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end