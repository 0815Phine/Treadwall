function cuewatch(t, ipc_dir, gate_state, softcode)
% Per-tick logic for the belt-visual-cue gate (started by gui_start_cuewatcher).
% Runs every tick during the session, including inside RunStateMachine.
%
% 1. When the live Bpod state first reaches the gate (gate_state), write
%    cue_arm.flag so the Python detector starts looking for the NEXT marker pass.
%    Arming on gate entry (rather than earlier) ensures the cue used is a fresh
%    crossing after direction has been read, not a stale pass during StartBuffer.
% 2. When the detector reports a crossing (cue_detected.flag), relay it to the
%    state machine as a soft code and finish. The gate then proceeds to the normal
%    trigger wait so zone 1 starts on the next hardware zone trigger.
%
% State (armed/done) is kept in the timer's UserData so it resets per session.
global BpodSystem

st = t.UserData;
if st.done, return; end

% Live current-state name (same source gui report uses; valid inside RunStateMachine).
sname = '';
try
    if isfield(BpodSystem.Status, 'CurrentStateName') && ~isempty(BpodSystem.Status.CurrentStateName)
        sname = BpodSystem.Status.CurrentStateName;
    end
catch
end

arm_flag = fullfile(ipc_dir, 'cue_arm.flag');
det_flag = fullfile(ipc_dir, 'cue_detected.flag');

% ── Arm the detector once we enter the gate ──────────────────────────────────
% Match by prefix so the forward/backward gate states (waitforCuef/waitforCueb)
% both arm from a single gate_state ('waitforCue').
if ~st.armed && ~isempty(sname) && startsWith(sname, gate_state)
    fid = fopen(arm_flag, 'w');
    if fid > 0, fprintf(fid, '1'); fclose(fid); end
    st.armed = true;
    fprintf('cue-watcher: armed (entered %s)\n', gate_state);
end

% ── Relay a detected crossing to the state machine ───────────────────────────
if st.armed && exist(det_flag, 'file')
    SendBpodSoftCode(softcode);
    delete(det_flag);
    st.done = true;
    fprintf('cue-watcher: cue detected -> SoftCode %d sent\n', softcode);
end

t.UserData = st;
end
