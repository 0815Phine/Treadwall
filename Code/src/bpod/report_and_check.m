function report_and_check(ipc_dir)
% Runs every 0.5 s during a session (incl. inside RunStateMachine). Reports the
% live Bpod state to the GUI and handles the emergency-stop flag.
global BpodSystem

% ── Report current state for the GUI ─────────────────────────────────────────
try
    sname = '';
    if isfield(BpodSystem.Status, 'CurrentStateName') && ~isempty(BpodSystem.Status.CurrentStateName)
        sname = BpodSystem.Status.CurrentStateName;
    elseif isfield(BpodSystem.Status, 'CurrentStateCode')
        % Fallback: map the live state code to a name via the running matrix.
        code = BpodSystem.Status.CurrentStateCode;
        if isprop(BpodSystem, 'StateMatrix') || isfield(BpodSystem, 'StateMatrix')
            names = BpodSystem.StateMatrix.StateNames;
            if code >= 1 && code <= numel(names), sname = names{code}; end
        end
    end
    if ~isempty(sname)
        fid = fopen(fullfile(ipc_dir, 'bpod_state.txt'), 'w');
        fprintf(fid, '%s', sname);
        fclose(fid);
    end
catch
end

% ── Emergency stop ───────────────────────────────────────────────────────────
f = fullfile(ipc_dir, 'emergency_stop.flag');
if exist(f, 'file')
    delete(f);
    BpodSystem.Status.BeingUsed = 0;
    SendBpodSoftCode(2);
end
end
