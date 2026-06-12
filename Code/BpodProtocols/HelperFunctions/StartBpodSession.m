function StartBpodSession(animal_id, session_id, datetime_str, protocol_name)
% Called by TreadwallGUI.py (or StartSession.ps1) to launch a session
% non-interactively.  After the protocol finishes this function stays alive,
% polling for a pending_session.json that the GUI writes when a new session
% is started — so MATLAB does not need to be restarted between sessions.

% ── Configuration (edit once) ─────────────────────────────────────────────
DATA_BASE = 'D:\';
IPC_DIR   = 'C:\Users\TomBombadil\Data\ipc';
% ──────────────────────────────────────────────────────────────────────────

% Signal to GUI that MATLAB is alive (heartbeat, also updated in wait loop below)
if ~exist(IPC_DIR, 'dir'), mkdir(IPC_DIR); end
fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
global BpodSystem

% Build paths
session_dir = fullfile(DATA_BASE, animal_id, session_id);
base_name   = sprintf('%s_%s_%s', animal_id, datetime_str, session_id);

% Ensure session directory exists
if ~exist(session_dir, 'dir')
    mkdir(session_dir)
end

% Initialise Bpod (only on the very first call — BpodSystem persists)
if isempty(BpodSystem)
    Bpod()
    % Hide the Bpod Launch Manager — the experiment GUI handles session control
    try
        set(BpodSystem.GUIHandles.MainFig, 'Visible', 'off');
    catch
        % Handle name may differ between Bpod versions; silently ignore
    end
end

% Pre-fill session identifiers — protocols read these via BpodSystem.GUIData
BpodSystem.GUIData.SubjectName = animal_id;
BpodSystem.GUIData.SessionID   = session_id;
BpodSystem.GUIData.DatetimeStr = datetime_str;

% Override data folder and session file path
BpodSystem.Path.DataFolder      = DATA_BASE;
BpodSystem.Path.CurrentDataFile = fullfile(session_dir, [base_name '_bpod.mat']);

% Run the selected Bpod protocol (blocks until the protocol function returns)
fprintf('Starting protocol: %s\n\n', protocol_name);
try
    feval(protocol_name)
catch e
    fprintf('Protocol error: %s\n', e.message);
    write_session_error(IPC_DIR, e.message);
end

% ── Multi-session waiting loop ────────────────────────────────────────────
% Stay alive so the user can start another session without restarting MATLAB.
% The GUI writes IPC_DIR/pending_session.json to trigger the next session.
% Close MATLAB (or press Ctrl+C) to quit at the end of the day.
if ~exist(IPC_DIR, 'dir'), mkdir(IPC_DIR); end
pending_file = fullfile(IPC_DIR, 'pending_bpod.json');

fprintf('\nProtocol finished. Waiting for next session (close MATLAB to quit).\n');
fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
while true
    pause(0.5);
    fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
    if exist(pending_file, 'file')
        try
            info = jsondecode(fileread(pending_file));
            delete(pending_file);

            % Update identifiers for the new session
            animal_id     = info.animal_id;
            session_id    = info.session_id;
            datetime_str  = info.datetime_str;
            protocol_name = info.protocol;

            new_session_dir = fullfile(DATA_BASE, animal_id, session_id);
            new_base_name   = sprintf('%s_%s_%s', animal_id, datetime_str, session_id);
            if ~exist(new_session_dir, 'dir'), mkdir(new_session_dir); end

            BpodSystem.GUIData.SubjectName  = animal_id;
            BpodSystem.GUIData.SessionID    = session_id;
            BpodSystem.GUIData.DatetimeStr  = datetime_str;
            BpodSystem.Path.CurrentDataFile = fullfile(new_session_dir, [new_base_name '_bpod.mat']);

            fprintf('Starting new session: %s\n\n', new_base_name);
            feval(protocol_name)
            fprintf('\nSession done. Waiting for next session...\n');
        catch e
            fprintf('Error starting new session: %s\n', e.message);
            write_session_error(IPC_DIR, e.message);
        end
    end
end

end

function write_session_error(ipc_dir, msg)
% Notify the GUI that a session failed to start/run so it can surface the
% error and reset its controls instead of appearing stuck.
try
    if ~exist(ipc_dir, 'dir'), mkdir(ipc_dir); end
    fid = fopen(fullfile(ipc_dir, 'session_error.json'), 'w');
    fprintf(fid, '%s', jsonencode(struct('message', msg)));
    fclose(fid);
catch
end
end
