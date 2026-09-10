function StartBpodSession(animal_id, session_id, datetime_str, protocol_name)
% Called by TreadwallGUI.py to launch a session
% non-interactively.  After the protocol finishes this function stays alive,
% polling for a pending_session.json that the GUI writes when a new session
% is started — so MATLAB does not need to be restarted between sessions.

% ── Configuration (from central config; edit treadwall_config.json) ───────
cfg       = treadwall_config();
DATA_BASE = cfg.paths.data_root;
IPC_DIR   = cfg.paths.ipc_dir;
% ──────────────────────────────────────────────────────────────────────────

% Signal to GUI that MATLAB is alive (heartbeat, also updated in wait loop below)
if ~exist(IPC_DIR, 'dir'), mkdir(IPC_DIR); end
fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
global BpodSystem

% An empty protocol_name means "pre-warm": initialise Bpod (and WaveSurfer) and
% drop straight into the waiting loop, without running a protocol or creating a
% session folder. The GUI sends the first real session via pending_bpod.json.
prewarm = isempty(protocol_name);

% Build paths
session_dir = fullfile(DATA_BASE, animal_id, session_id);
base_name   = sprintf('%s_%s_%s', animal_id, datetime_str, session_id);

% Ensure session directory exists (skip for pre-warm — no session yet)
if ~prewarm && ~exist(session_dir, 'dir')
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
if ~prewarm
    BpodSystem.Path.CurrentDataFile = fullfile(session_dir, [base_name '_bpod.mat']);
end

% Run the selected Bpod protocol (blocks until the protocol function returns).
% For a pre-warm, skip this and go straight to the waiting loop below.
if ~prewarm
    fprintf('Starting protocol: %s\n\n', protocol_name);
    try
        feval(protocol_name)
    catch e
        fprintf('Protocol error: %s\n', e.message);
        write_session_error(IPC_DIR, e.message);
    end
else
    fprintf('Bpod ready (pre-warm). Waiting for the first session from the GUI...\n');
end

% ── Connect / disconnect / reconnect cycle ────────────────────────────────
% Stay alive so the user can start another session without restarting MATLAB.
% The GUI writes pending_bpod.json to trigger the next session, shutdown.flag to
% disconnect Bpod, and reconnect.flag to bring it back (e.g. after fixing code).
% Close MATLAB to quit at the end of the day.
if ~exist(IPC_DIR, 'dir'), mkdir(IPC_DIR); end
pending_file   = fullfile(IPC_DIR, 'pending_bpod.json');
shutdown_file  = fullfile(IPC_DIR, 'shutdown.flag');
reconnect_file = fullfile(IPC_DIR, 'reconnect.flag');
ready_file     = fullfile(IPC_DIR, 'bpod_ready.flag');
quit_file      = fullfile(IPC_DIR, 'quit.flag');   % GUI closed -> release MATLAB

quitting = false;
while true   % outer cycle: connected -> disconnected -> (reconnected) -> ...
    % Bpod (and WaveSurfer, launched first) are up and ready for sessions.
    print_ready_message();
    fclose(fopen(ready_file, 'w'));   % tell the GUI: WaveSurfer + Bpod ready
    fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));

    % ── Main session wait loop ──
    while true
        pause(0.5);
        fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
        if exist(quit_file, 'file')
            delete(quit_file);
            quitting = true;
            break
        end
        if exist(shutdown_file, 'file')
            delete(shutdown_file);
            break
        end
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
                print_ready_message();
            catch e
                fprintf('Error starting new session: %s\n', e.message);
                write_session_error(IPC_DIR, e.message);
            end
        end
    end

    % ── Clean disconnect (triggered by the GUI "Disconnect Bpod" button) ───
    fprintf('\nDisconnecting Bpod...\n');
    if exist(ready_file, 'file'), delete(ready_file); end   % no longer ready
    try, BpodSystem.Status.BeingUsed = 0; catch, end % avoid "running protocol" dialog in EndBpod
    try
        EndBpod;   % gracefully stops+deletes Bpod's own AnalogTimer/PortRelayTimer
    catch e
        fprintf('EndBpod error: %s\n', e.message);
    end
    % Mop up leftover non-Bpod timers (e.g. a stray protocol timer) but PRESERVE
    % the tagged WaveSurfer IPC timer, so WaveSurfer stays responsive across a
    % reconnect. EndBpod already removed Bpod's own timers.
    try
        stray = timerfindall;
        if ~isempty(stray)
            tags = get(stray, 'Tag');
            if ischar(tags), tags = {tags}; end
            delete(stray(~strcmp(tags, 'treadwall_ws_ipc')));
        end
    catch
    end
    % Bpod is released. If the GUI asked to quit, fully leave the loop now.
    if quitting
        release_matlab(IPC_DIR);
        break
    end

    try, fclose(fopen(fullfile(IPC_DIR, 'bpod_disconnected.flag'), 'w')); catch, end
    % Persistent marker so a GUI reopened during standby knows to offer Reconnect.
    standby_file = fullfile(IPC_DIR, 'bpod_standby.flag');
    try, fclose(fopen(standby_file, 'w')); catch, end
    fprintf(['Bpod disconnected. Press "Reconnect Bpod" ' ...
        'in the GUI, or close the GUI to free MATLAB.\n']);

    % ── Standby: wait for the GUI Reconnect button (or GUI close) ──────────
    while true
        pause(0.5);
        fclose(fopen(fullfile(IPC_DIR, 'matlab_alive.flag'), 'w'));
        if exist(quit_file, 'file')
            delete(quit_file);
            quitting = true;
            break
        end
        if exist(reconnect_file, 'file')
            delete(reconnect_file);
            fprintf('\nReconnecting Bpod...\n');
            try
                Bpod()
                % Refresh the global link: EndBpod did 'clear global BpodSystem',
                % which can leave this function's BpodSystem stale so the console
                % hide below silently fails. Re-bind to the object Bpod() created.
                clear BpodSystem
                global BpodSystem %#ok<TLEV>
                try
                    set(BpodSystem.GUIHandles.MainFig, 'Visible', 'off');
                catch
                end
                if exist(standby_file, 'file'), delete(standby_file); end
                fprintf('Bpod reconnected.\n');
                break   % leave standby -> outer loop resumes the main wait loop
            catch e
                fprintf('Reconnect error: %s\n', e.message);
                write_session_error(IPC_DIR, e.message);
                % stay in standby so the user can fix the issue and retry
            end
        end
    end

    % Quit requested while in standby (Bpod already disconnected) — release now.
    if quitting
        release_matlab(IPC_DIR);
        break
    end
end

end

function release_matlab(ipc_dir)
% The GUI was closed: fully leave the connect/standby loop so MATLAB returns to a
% normal command prompt. Stop the WaveSurfer IPC timer too and clear state flags.
try, delete(timerfindall); catch, end
flags = {'bpod_ready.flag', 'bpod_standby.flag', 'bpod_disconnected.flag', ...
    'matlab_alive.flag', 'quit.flag'};
for k = 1:numel(flags)
    f = fullfile(ipc_dir, flags{k});
    try, if exist(f, 'file'), delete(f); end, catch, end
end
fprintf('MATLAB released — returning to the command prompt.\n');
end

function print_ready_message()
% Same message after every session so the operator always sees the same two
% options in the console: start another session, or disconnect + close.
fprintf('\n');
fprintf('============================================================\n');
fprintf(' Session finished. In the Treadwall GUI you can now:\n');
fprintf('   - start a NEW SESSION, or\n');
fprintf('   - click "Disconnect Bpod", then close the GUI.\n');
fprintf('============================================================\n');
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
