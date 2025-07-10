function Treadwall_Camera
% this script can be used to test proper starting and stopping of the camera
% the main loop iterating through the trials is removed from this protocol

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = 'C:\Users\TomBombadil\Desktop\Animals\Cohort00_Test'; %Tests should always be saved in this folder

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

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
RunStateMachine;

disp('Synced with Wavesurfer.');

%% ---------- Synching with WaveSurfer ------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'Camera Running', ...
    'Timer',60,...
    'StateChangeConditions', {'Tup', 'StopCamera'},...
    'OutputActions', {});
sma = AddState(sma, 'Name', 'StopCamera', ...
    'Timer', 1,...
    'StateChangeConditions', {'Tup', 'exit'},...
    'OutputActions', {'BNC1',1});
SendStateMachine(sma);
disp('Test running...');
RunStateMachine;

disp('Loop end');
disp('Stop wavesurfer. Stop Bpod');
end