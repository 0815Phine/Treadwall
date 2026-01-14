function Treadwall_Habituation_1
% iterating through half of the travel length
% stay in each phase for 200s

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

% load parameters
params_file = fullfile([BpodSystem.Path.ProtocolFolder '\treadwall_habituation1_parameters.m']);
run(params_file)

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    S.GUI.stimDur = stimDur; %in seconds
    S.GUI.ITIDur = ITIDur; %in seconds
    S.GUI.ScalingFactor = 1;
    S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
    S.GUIMeta.EmergencyStop.Style = 'pushbutton';
    %S.GUI.ExpInfoPath = start_path;

    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

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

R.startUSBStream()

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
    disp(' ');
    disp('- - - - - - - - - - - - - - - ');
    disp(['Trial: ' num2str(currentTrial) ' - ' datestr(now,'HH:MM:SS')]);

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
    if ~isempty(fieldnames(RawEvents)) %If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
        BpodSystem.Data.TrialSettings(currentTrial) = S;
        %BpodSystem.Data.TrialTypes(currentTrial) = triallist(currentTrial);
        SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
        SaveBpodProtocolSettings;
    end

    if BpodSystem.Status.BeingUsed == 0
        disp('Session ended via Bpod Console. Current trial data has not been saved')
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

disp('Stop wavesurfer. Stop Bpod');
end