function d = treadwall_params_dir()
% Absolute path to the Bpod parameter files (Code/parameters/bpod), derived
% relative to this helper's own location so it works from any machine/checkout.
% Single source of truth for where protocols read their *_parameters.m files.
% This file lives in Code/src/bpod, so the repo's Code/ root is two levels up;
% the parameter files live under Code/parameters/bpod.
this_dir  = fileparts(mfilename('fullpath'));   % Code/src/bpod
code_root = fileparts(fileparts(this_dir));     % Code
d = fullfile(code_root, 'parameters', 'bpod');
end
