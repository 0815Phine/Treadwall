function S = gui_readparams(S, ipc_dir)
% Read live parameter edits the GUI wrote to protocol_params.json and apply them
% to S.GUI. Call once at the top of each trial. Only fields the protocol already
% exposes (present in S.GUI) are updated, so unrelated keys are ignored.
params_file = fullfile(ipc_dir, 'protocol_params.json');
if exist(params_file, 'file')
    try
        p = jsondecode(fileread(params_file));
        for name = {'ITIDur', 'stimDur', 'ScalingFactor'}
            f = name{1};
            if isfield(p, f) && isfield(S, 'GUI') && isfield(S.GUI, f)
                S.GUI.(f) = p.(f);
            end
        end
    catch
    end
end
end
