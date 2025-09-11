function StopButton

global BpodSystem

%% ---------- Define task parameters --------------------------------------
start_path = 'C:\Users\TomBombadil\Desktop\Animals\Cohort00_Test'; %Tests should always be saved in this folder

% initialize parameters
S = struct(); %BpodSystem.ProtocolSettings;

if isempty(fieldnames(S))
    freshGUI = 1;        %flag to indicate that prameters have not been loaded from previous session.
    S.GUI.SubjectID = BpodSystem.GUIData.SubjectName;
    S.GUI.SessionID = BpodSystem.GUIData.SessionID;
    S.GUI.EmergencyStop = 'SendBpodSoftCode(2)';
    S.GUIMeta.EmergencyStop.Style = 'pushbutton';
    session_dir = ([start_path '\' S.GUI.SubjectID '\' S.GUI.SessionID]);

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Run for 30 Minute --------------------------------------------
sma = NewStateMachine();
sma = AddState(sma, 'Name', 'ExperimentRunning', ...
    'Timer',1800,...
    'StateChangeConditions', {'Tup', 'exit', 'SoftCode2', 'exit'},...
    'OutputActions', {});
SendStateMachine(sma);
disp('Test running...');
RawEvents = RunStateMachine;

if ~isempty(fieldnames(RawEvents)) %If trial data was returned
    BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); %Computes trial events from raw data
    BpodSystem.Data.TrialSettings = S;
    SaveBpodSessionData; %Saves the field BpodSystem.Data to the current data file
    SaveBpodProtocolSettings;
end

if BpodSystem.Status.BeingUsed == 0
    return
end

disp('Loop end');
disp('Stop Bpod');
end