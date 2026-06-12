function Treadwall_scrambled
%

global BpodSystem

%% ---------- IPC setup ---------------------------------------------------
ipc_dir = 'C:\Users\TomBombadil\Data\ipc';
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
% Clear any stale emergency-stop flag left over from a previous session so it
% cannot immediately abort this one.
estop_flag = fullfile(ipc_dir, 'emergency_stop.flag');
if exist(estop_flag, 'file'), delete(estop_flag); end

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

% load correct parameters for location
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
    S.GUI.ITIDur = 1; %ITIDur; %in seconds
    S.GUI.stimDur = 1; %stimDur; %in seconds
    S.GUI.ScalingFactor = 1;
    S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
    S.GUIMeta.EmergencyStop.Style = 'pushbutton';
    %S.GUI.ExpInfoPath = start_path;

    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);
    % Use datetime from StartSession.ps1 if available, so all file names match
    if isfield(BpodSystem.GUIData, 'DatetimeStr') && ~isempty(BpodSystem.GUIData.DatetimeStr)
        datetime_str = BpodSystem.GUIData.DatetimeStr;
    else
        datetime_str = datestr(now, 'yyyymmdd_HHMM');
    end
    base_name = sprintf('%s_%s_%s', S.GUI.SubjectID, datetime_str, S.GUI.SessionID);
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;
try, close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

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

R.startUSBStream()

%% ---------- Emergency-stop watcher --------------------------------------
% Poll for the GUI emergency-stop flag from here on, so the button works even
% while waiting for WaveSurfer. onCleanup guarantees the timer is removed on
% every exit path (normal end, early return, or error).
t_estop = timer('Period', 0.5, 'ExecutionMode', 'fixedRate', ...
    'TimerFcn', @(~,~) check_estop(ipc_dir));
estopCleanup = onCleanup(@() stop_estop_timer(t_estop)); %#ok<NASGU>
start(t_estop);

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
% Without this check the code enters the main loop and crashes on destroyed GUI handles.
if BpodSystem.Status.BeingUsed == 0
    disp('Session stopped while waiting for WaveSurfer. Exiting cleanly.');
    W.setFixedVoltage([1 2], 0);
    R.stopUSBStream();
    % Tell WaveSurfer to stop/rename (in case recording had already started)
    % and the GUI that the session is done. onCleanup removes the estop timer.
    fclose(fopen(fullfile(ipc_dir, 'stop_wavesurfer.flag'), 'w'));
    fclose(fopen(fullfile(ipc_dir, 'session_done.flag'), 'w'));
    return
end

disp('Synced with Wavesurfer.');

%% ---------- Main Loop ---------------------------------------------------
try
for currentTrial = 1:S.GUI.MaxTrialNumber
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS') ' - ' 'Type: ' triallist{currentTrial}]);

    % Read parameter updates from Python GUI
    params_file = fullfile(ipc_dir, 'protocol_params.json');
    if exist(params_file, 'file')
        try
            p = jsondecode(fileread(params_file));
            if isfield(p, 'ITIDur'),        S.GUI.ITIDur        = p.ITIDur;        end
            if isfield(p, 'stimDur'),       S.GUI.stimDur       = p.stimDur;       end
            if isfield(p, 'ScalingFactor'), S.GUI.ScalingFactor = p.ScalingFactor; end
        catch, end
    end

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
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        BpodSystem.Data.TrialSettings(currentTrial) = S;
        BpodSystem.Data.TrialTypes(currentTrial) = triallist(currentTrial);
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        %SaveBpodProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0
        disp('Session stopped (emergency stop or Bpod Console). Partial trial data saved.')
        W.setFixedVoltage([1 2], 0)
        break
    end
end
catch e
    fprintf('Protocol error on trial %d: %s\n', currentTrial, e.message);
end

stop_estop_timer(t_estop);
BpodSystem.Status.BeingUsed = 0;
try, close(BpodSystem.ProtocolFigures.ParameterGUI); catch, end

clear arduino
disp('Loop end');

disp('Saving Rotary Encoder Data...')
RotData = R.readUSBStream();
rotary_src = fullfile(session_dir, [base_name '_bpod_rotdata.mat']);
save(rotary_src, 'RotData')
R.stopUSBStream()

% Signal the GUI: session complete, stop WaveSurfer
if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
fclose(fopen(fullfile(ipc_dir, 'stop_wavesurfer.flag'), 'w'));
fclose(fopen(fullfile(ipc_dir, 'session_done.flag'), 'w'));
disp('Session complete. WaveSurfer stopping automatically.');
end

function check_estop(ipc_dir)
f = fullfile(ipc_dir, 'emergency_stop.flag');
if exist(f, 'file')
    delete(f);
    global BpodSystem
    BpodSystem.Status.BeingUsed = 0;
    SendBpodSoftCode(2);
end
end

function stop_estop_timer(t)
% Safely stop and delete the emergency-stop timer on any exit path
% (idempotent — guards against an already-deleted timer).
try
    if isvalid(t)
        stop(t);
        delete(t);
    end
catch
end
end