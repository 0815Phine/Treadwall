function StartBpodSession(animal_id, session_id, datetime_str, protocol_name)
% Called by StartSession.ps1 to launch a session non-interactively.
% Initialises Bpod, pre-fills subject/session/datetime, opens WaveSurfer,
% then hands off to the selected Bpod protocol.

% ── Configuration (edit once) ─────────────────────────────────────────────
DATA_BASE = 'D:\Animals';    % Base folder for all behavioural data (no cohort subfolder)
% ──────────────────────────────────────────────────────────────────────────

global BpodSystem

% Build paths
session_dir = fullfile(DATA_BASE, animal_id, session_id);
base_name   = sprintf('%s_%s_%s', animal_id, datetime_str, session_id);

% Ensure session directory exists
if ~exist(session_dir, 'dir')
    mkdir(session_dir)
end

% Initialise Bpod
Bpod()

% Pre-fill session identifiers — protocols read these via BpodSystem.GUIData
BpodSystem.GUIData.SubjectName = animal_id;
BpodSystem.GUIData.SessionID   = session_id;
BpodSystem.GUIData.DatetimeStr = datetime_str;    % picked up by protocols

% Override data folder and session file path (Bpod sets these during Bpod()
% before we can override, so we set both explicitly here)
BpodSystem.Path.DataFolder    = DATA_BASE;
BpodSystem.Path.CurrentDataFile = fullfile(session_dir, [base_name '_bpod.mat']);

% Run the selected Bpod protocol
fprintf('Starting protocol: %s\n\n', protocol_name);
feval(protocol_name)

end
