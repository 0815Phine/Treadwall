function Treadwall_scrambled
%

global BpodSystem

%% ---------- IPC setup ---------------------------------------------------
ipc_dir = gui_ipc_dir();
gui_session_init(ipc_dir);

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % folder selected in GUI;

% initialize parameters
S = struct();

% load parameters
params_file = fullfile([BpodSystem.Path.ProtocolFolder '\parameters\treadwall_sc_p_parameters.m']);
run(params_file)

% ------ GUI parameters
S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
S.GUI.SessionID = BpodSystem.GUIData.SessionID;
S.GUI.ITIDur = ITI_DUR; %in seconds
S.GUI.stimDur = STIM_DUR; %in seconds
S.GUI.ScalingFactor = 1;
S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
S.GUIMeta.EmergencyStop.Style = 'pushbutton';

session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);

% get base name
if isfield(BpodSystem.GUIData, 'DatetimeStr') && ~isempty(BpodSystem.GUIData.DatetimeStr)
    % Use datetime from the GUI if available, so all file names match
    datetime_str = BpodSystem.GUIData.DatetimeStr;
else
    datetime_str = datestr(now, 'yyyymmdd_HHMM');
end
base_name = sprintf('%s_%s_%s', S.GUI.SubjectID, datetime_str, S.GUI.SessionID);

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

% Publish the protocol-loaded parameters so the GUI shows them as its initial spinbox values.
gui_publish_loaded_params(ipc_dir, S);

%% ---------- Create Triallist and load Trials ----------------------------
% create triallist (adjust function according to trials needed)
create_triallist_adaptable(session_dir, base_name); % not all offsets used, for all use "create_triallist_all"

% read triallist
trialList_Info = dir(fullfile(session_dir, [base_name '_triallist.csv']));
if isempty(trialList_Info)
    [triallist_file, triallist_path] = uigetfile(fullfile(start_path,'*.csv'));
    if isequal(triallist_file, 0)
        error('No triallist selected. Aborting.');
    end
    triallist_dir = fullfile(triallist_path, triallist_file);
else
    triallist_dir = fullfile(trialList_Info.folder, trialList_Info.name);
end

triallist = readtable(triallist_dir);
triallist = triallist.type;
S.GUI.MaxTrialNumber = numel(triallist);

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
%R.streamUI() % uncomment for live streaming position, good for troubleshooting

%% ---------- Analog Output Module ----------------------------------------
try
    W = BpodWavePlayer(BpodSystem.ModuleUSB.WavePlayer1);
catch
    error(['The Analog Output Module is not coupled to the correct COM, ' ...
        'check the Bpod Console!'])
end

W.SamplingRate = 100;%in kHz
W.OutputRange = '0V:5V';
W.TriggerMode = 'Normal';

% Waveforms for distances (waveforms are loaded with the parameter file)
lengthWave = S.GUI.stimDur*W.SamplingRate;
for i = 1:length(WAVEFORMS)
    W.loadWaveform(i, WAVEFORMS{i}*ones(1,lengthWave));
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
    gui_signal_aborted(ipc_dir);
    return
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:S.GUI.MaxTrialNumber
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' triallist{currentTrial}]);

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

    % read output action
    stimOutput = GetStimOutput(triallist{currentTrial});

    % construct state machine
    sma = NewStateMachine(); %Assemble new state machine description

    % first trial: with start buffer
    if currentTrial == 1
        sma = AddState(sma, 'Name', 'StartBuffer', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'stimulus', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'iti', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', stimOutput});

        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'exit', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

        sma = AddState(sma, 'Name', 'StopCamera', ...
            'Timer', 1,...
            'StateChangeConditions', {'Tup', 'exit'},...
            'OutputActions', {'BNC1',1});

    % last trial: with end buffer and stopping camera
    elseif currentTrial == S.GUI.MaxTrialNumber
        sma = AddState(sma, 'Name', 'stimulus', ...
            'Timer', S.GUI.stimDur,...
            'StateChangeConditions', {'Tup', 'EndBuffer', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', stimOutput});

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
            'StateChangeConditions', {'Tup', 'iti', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', stimOutput});

        sma = AddState(sma, 'Name', 'iti', ...
            'Timer', S.GUI.ITIDur,...
            'StateChangeConditions', {'Tup', 'exit', 'SoftCode2', 'StopCamera'},...
            'OutputActions', {'WavePlayer1', ['!' 3 0 0]});

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
        BpodSystem.Data.TrialTypes(currentTrial) = triallist(currentTrial);
        SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
    end

    if BpodSystem.Status.BeingUsed == 0
        disp('Session stopped (emergency stop or Bpod Console). Partial trial data saved.')
        W.setFixedVoltage([1 2], 0)
        break
    end
end

stop_estop_timer(t_estop);
BpodSystem.Status.BeingUsed = 0;
try close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

clear arduino
disp('Loop end');

disp('Saving Rotary Encoder Data...')
RotData = R.readUSBStream();
rotary_src = fullfile(session_dir, [base_name '_bpod_rotdata.mat']);
save(rotary_src, 'RotData')
R.stopUSBStream()

% Signal the GUI: session complete, stop WaveSurfer
gui_signal_done(ipc_dir);
disp('Session complete. WaveSurfer stopping automatically.');
end