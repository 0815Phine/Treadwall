function Treadwall_Habituation_1
% iterating through half of the travel length
% stay in each phase for 200s

global BpodSystem

%% ---------- IPC setup ---------------------------------------------------
ipc_dir = gui_ipc_dir();
gui_session_init(ipc_dir);

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % folder selected in GUI;

% initialize parameters
S = struct();

% load parameters
params_file = fullfile([BpodSystem.Path.ProtocolFolder '\treadwall_habituation1_parameters.m']);
run(params_file)

% ------ GUI parameters
S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
S.GUI.SessionID = BpodSystem.GUIData.SessionID;
S.GUI.stimDur = stimDur; %in seconds
S.GUI.ITIDur = ITIDur; %in seconds
S.GUI.ScalingFactor = 1;
S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
S.GUIMeta.EmergencyStop.Style = 'pushbutton';

session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

% Publish the protocol-loaded parameters so the GUI shows them as its initial spinbox values.
gui_publish_loaded_params(ipc_dir, S);

%% ---------- Arduino Synchronizer ----------------------------------------
COM = 'COM9';
try
    arduino = serialport(COM, 115385);
catch
    error('The Arduino is not connected to %s, select the correct COM!', COM)
end

% Send initial value to Arduino
scalingValue = S.GUI.ScalingFactor;
writeline(arduino, strcat(num2str(scalingValue), '\n'));
lastScalingFactor = scalingValue;

%% ---------- Rotary Encoder Module ---------------------------------------
try
    R = RotaryEncoderModule(BpodSystem.ModuleUSB.RotaryEncoder1);
catch
    error(['The Rotary Encoder Module is not coupled to the correct COM, ' ...
        'check the Bpod Console!'])
end

%R.startUSBStream() -> moved to after restarting timer for proper alignment
%R.streamUI() % for live streaming position, good for troubleshooting

%% ---------- Analog Output Module ----------------------------------------
try
    W = BpodWavePlayer(BpodSystem.ModuleUSB.WavePlayer1);
catch
    error(['The Analog Output Module is not coupled to the correct COM, ' ...
        'check the Bpod Console!'])
end

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Master';

% load waveforms (part of parameter file)
lengthWave = (S.GUI.stimDur+5)*W.SamplingRate; % add 5 second buffer
for i = 1:length(waveforms)
    W.loadWaveform(i, waveforms{i}*ones(1,lengthWave));
end

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
    W.setFixedVoltage([1 2], 0);
    R.stopUSBStream();
    gui_signal_done(ipc_dir);
    return
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:floor(length(waveforms)/2)
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS')]);

    % Read live parameter edits from the GUI
    S = gui_read_params(S, ipc_dir);

    % Get current Scaling value
    scalingValue = S.GUI.ScalingFactor;
    % If changed, update Arduino
    if scalingValue ~= lastScalingFactor
        writeline(arduino, strcat(num2str(scalingValue), '\n'));
        lastScalingFactor = scalingValue;
        fprintf('Updated Arduino with new ScalingFactor: %.1f \n', scalingValue);
    end

    % construct state machine
    sma = NewStateMachine();

    % first trial
    if currentTrial == 1
        sma = AddState(sma, 'Name', 'Baseline', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'stimulus', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'exit', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['>' currentTrial-1 currentTrial-1 255 255]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 1,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});

    % last trial
    elseif currentTrial == floor(length(waveforms)/2)
        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'EndBuffer', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['>' currentTrial-1 currentTrial-1 255 255]});

        sma = AddState(sma, 'Name', 'EndBuffer', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'StopCamera', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 1,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});

    else
        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'exit', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['>' currentTrial-1 currentTrial-1 255 255]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 1,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});
    end

    % run state machine
    SendStateMachine(sma);
    RawEvents = RunStateMachine();
    if ~isempty(fieldnames(RawEvents)) % If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
        BpodSystem.Data.TrialSettings(currentTrial) = S;
        SaveBpodSessionData; %S aves the field BpodSystem.Data to the current data file
        SaveBpodProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0
        disp('Session stopped (emergency stop or Bpod Console). Partial trial data saved.')
        W.setFixedVoltage([1 2], 0)
        break
    end
end

clear arduino
disp('Loop end');

disp('Saving Rotary Encoder Data...')
RotData = R.readUSBStream();
save([session_dir '\RotData'],'RotData')
R.stopUSBStream()

BpodSystem.Status.BeingUsed = 0;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

% Signal the GUI: session complete, stop WaveSurfer
gui_signal_done(ipc_dir);
disp('Session complete. WaveSurfer stopping automatically.');
end