function Treadwall_Baseline
% just starts camera and 2P, no lateral wall movement
% runs for 20min and stops

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = BpodSystem.Path.DataFolder; % 'C:\Users\TomBombadil\Desktop\Animals' - Folder of current cohort selected in GUI;

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
    S.GUIMeta.EmergencyStop.Style = 'pushbutton';
    %S.GUI.ScalingFactor = 1;
    %S.GUI.ExpInfoPath = start_path;

    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Rotary Encoder Module ---------------------------------------
try
    R = RotaryEncoderModule(BpodSystem.ModuleUSB.RotaryEncoder1);
catch
    error(['The Rotary Encoder Module is not coupled to the correct COM, ' ...
        'check the Bpod Console!'])
end

%R.startUSBStream() -> moved to after restarting timer for proper alignment
%R.streamUI() % for live streaming position, good for troubleshooting

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

if ~isempty(fieldnames(RawEvents)) %If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
    BpodSystem.Data.TrialSettings(1) = S;
    SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
    SaveBpodProtocolSettings;
    RotData = R.readUSBStream();
end

if BpodSystem.Status.BeingUsed == 0
    disp('Session ended via Bpod Console. Current trial data has not been saved')
    return
end

disp('Experiment end');

disp('Saving Rotary Encoder Data...')
save([session_dir '\RotData'],'RotData')
R.stopUSBStream()

disp('Stop wavesurfer. Stop Bpod');
end
