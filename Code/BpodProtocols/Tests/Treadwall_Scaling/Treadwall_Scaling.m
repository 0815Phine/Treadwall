function Treadwall_Scaling
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

    % Variables
    S.GUI.ScalingFactor = 1;

    %S.GUI.ExpInfoPath = start_path;
else
    freshGUI  = 0;        %flag to indicate that prameters have been loaded from previous session.
end

BpodParameterGUI('init', S);
BpodSystem.ProtocolSettings = S;

%% ---------- Arduino Synchronizer ----------------------------------------
arduino = serialport('COM7', 115385);

% Send initial value to Arduino
scalingValue = S.GUI.ScalingFactor;
writeline(arduino, strcat(num2str(scalingValue), '\n'));
lastScalingFactor = scalingValue;

%% ---------- Restart Timer -----------------------------------------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Main Loop ---------------------------------------------------
% construct state machine
for i = 1:5
    S = BpodParameterGUI('sync', S);

    % Get current Scaling value
    scalingValue = S.GUI.ScalingFactor;
    % If changed, update Arduino
    if scalingValue ~= lastScalingFactor
        writeline(arduino, strcat(num2str(scalingValue), '\n'));
        lastScalingFactor = scalingValue;
        fprintf('Updated Arduino with new ScalingFactor: %.1f \n', scalingValue);
    end

    sma = NewStateMachine(); %Assemble new state machine description

    sma = AddState(sma, 'Name', 'StartBuffer', ...
        'Timer', 5,...
        'StateChangeConditions', {'Tup', 'Stimulus'},...
        'OutputActions', {});

    sma = AddState(sma, 'Name', 'Stimulus', ...
        'Timer', 5,...
        'StateChangeConditions', {'Tup', 'EndBuffer'},...
        'OutputActions', {});

    sma = AddState(sma, 'Name', 'EndBuffer', ...
        'Timer', 5,...
        'StateChangeConditions', {'Tup', 'exit'},...
        'OutputActions', {});

    % run state machine
    SendStateMachine(sma);
    RunStateMachine;
end

clear arduino
disp('Loop end');
disp('Close Stream. Stop Bpod');
end