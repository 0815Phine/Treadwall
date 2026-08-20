function Treadwall_Baseline
% just starts camera and 2P, no lateral wall movement
% runs for 20min and stops

global BpodSystem

%% ---------- IPC setup ---------------------------------------------------
ipc_dir = gui_ipc_dir();
gui_session_init(ipc_dir);

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % folder selected in GUI;

% initialize parameters
S = struct();

% ------ GUI parameters
S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
S.GUI.SessionID = BpodSystem.GUIData.SessionID;
S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
S.GUIMeta.EmergencyStop.Style = 'pushbutton';
S.GUI.ScalingFactor = 1; % can not be updated during session (sesison is one trial)

session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

% Publish the protocol-loaded parameters so the GUI shows them as its initial spinbox values
gui_publish_loaded_params(ipc_dir, S);

%% ---------- Rotary Encoder Module ---------------------------------------
try
    R = RotaryEncoderModule(BpodSystem.ModuleUSB.RotaryEncoder1);
catch
    error(['The Rotary Encoder Module is not coupled to the correct COM, ' ...
        'check the Bpod Console!'])
end

%R.startUSBStream() -> moved to after restarting timer for proper alignment
%R.streamUI() % for live streaming position, good for troubleshooting

%% ---------- Restart Timer -----------------------------------------------
% Discard any stale bytes left in the Bpod serial buffer (e.g. after an
% emergency stop) so the clock-reset confirmation byte is read correctly.
nStale = BpodSystem.SerialPort.bytesAvailable;
if nStale > 0, BpodSystem.SerialPort.read(nStale, 'uint8'); end
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

% start rotary encoder stream
R.startUSBStream()

%% ---------- Emergency-stop watcher --------------------------------------
% Poll for the GUI emergency-stop flag
% onCleanup guarantees the timer is removed on every exit path (normal end, early return, or error).
t_estop = gui_start_estop_timer(ipc_dir);
estopCleanup = onCleanup(@() stop_estop_timer(t_estop));

%% ---------- Synching with WaveSurfer ------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'WaitForWaveSurfer', ...
    'Timer',0,...
    'StateChangeConditions', {'BNC1High', 'exit', 'SoftCode2', 'exit'},...
    'OutputActions', {});
SendStateMachine(sma);
disp('Waiting for Wavesurfer...');
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) % If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
    SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
end

% Clean exit if user stopped Bpod while waiting for WaveSurfer.
if BpodSystem.Status.BeingUsed == 0
    disp('Session stopped while waiting for WaveSurfer. Exiting cleanly.');
    R.stopUSBStream();
    gui_signal_done(ipc_dir);
    return
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'ExperimentRunning', ...
    'Timer',1200,...
    'StateChangeConditions', {'Tup', 'StopCamera', 'SoftCode2', 'StopCamera'},...
    'OutputActions', {});
sma = AddState(sma, 'Name', 'StopCamera', ...
    'Timer', 1,...
    'StateChangeConditions', {'Tup', 'exit'},...
    'OutputActions', {'BNC1',1});
SendStateMachine(sma);
disp('Experiment running...');
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) % If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
    BpodSystem.Data.TrialSettings(1) = S;
    SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
    SaveBpodProtocolSettings;
    RotData = R.readUSBStream();
end

if BpodSystem.Status.BeingUsed == 0
    disp('Session stopped (emergency stop or Bpod Console). Partial data saved.')
    RotData = R.readUSBStream();
else
    disp('Experiment end');
end

if exist('RotData', 'var')
    disp('Saving Rotary Encoder Data...')
    rotary_src = fullfile(session_dir, [base_name '_bpod_rotdata.mat']);
    save(rotary_src, 'RotData')
    R.stopUSBStream()
    save([session_dir '\RotData'],'RotData')
else
    Warning('No rotary encoder data recorded')
end
R.stopUSBStream()

BpodSystem.Status.BeingUsed = 0;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

% Signal the GUI: session complete, stop WaveSurfer
gui_signal_done(ipc_dir);
disp('Session complete. WaveSurfer stopping automatically.');
end
