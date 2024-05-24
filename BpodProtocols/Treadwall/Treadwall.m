function Treadwall

global BpodSystem

%% ---------- Define protocol settings ------------------------------------
% initialize parameters
S = BpodSystem.ProtocolSettings;
stimDur =
ITIDur =

% define trials
maxTrials = 

% randomize output actions
stimOutput =

%% ---------- Analog Output Module ----------------------------------------
BpodSystem.assertModule({},);
W = BpodWavePlayer('');

%% ---------- Restart Timer and start Rotary Encoder Stream ---------------
BpodSystem.SerialPort.write('*', 'uint8');
Confirmed = BpodSystem.SerialPort.read(1,'uint8');
if Confirmed ~= 1, error('Faulty clock reset'); end

%% ---------- Main Loop ---------------------------------------------------
for currentTrial = 1:maxTrials
    S = BpodParameterGUI('sync', S);

    % read output action
    switch typeList{currentTrial}
        case 'C'
            stimOutput = {};
        case 'L'
            stimOutput = {};
        case 'R'
            stimOutput = {};
    end

    % construct state machine
    sma = NewStateMachine(); % Assemble new state machine description

    sma = AddState(sma, 'Name', 'iti', ...
        'Timer', ITIDur,...
        'StateChangeConditions', {'Tup', 'stimulus'},...
        'OutputActions', );

    sma = AddState(sma, 'Name', 'stimulus', ...
        'Timer', stimDur,...
        'StateChangeConditions', {'Tup', 'iti'},...
        'OutputActions', stimOutput);

    SendStateMachine(sma);
    RawEvents = RunStateMachine;
    if ~isempty(fieldnames(RawEvents)) % If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
        SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
    end

    if BpodSystem.Status.BeingUsed == 0; return; end
end