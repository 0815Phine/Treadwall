function gui_publishloadedparams(ipc_dir, S)
% Publish the protocol-loaded parameters so the GUI shows them as the initial
% values in its spinboxes. The GUI must NOT pre-seed protocol_params.json; it
% ingests this file instead, and only writes protocol_params.json back when the
% user edits a value.
%
% Only the parameters the protocol actually exposes (present in S.GUI) are
% published, so protocols with fewer params (e.g. Baseline, predictable) work
% without change.
try
    lp = struct();
    for name = {'ITIDur', 'stimDur', 'ScalingFactor'}
        f = name{1};
        if isfield(S, 'GUI') && isfield(S.GUI, f)
            lp.(f) = S.GUI.(f);
        end
    end
    fid = fopen(fullfile(ipc_dir, 'loaded_params.json'), 'w');
    fprintf(fid, '%s', jsonencode(lp));
    fclose(fid);
catch
end
end
