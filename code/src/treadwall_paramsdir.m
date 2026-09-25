function d = treadwall_paramsdir()
% Absolute path to the Bpod parameter files (code/parameters/bpod), derived
% relative to this helper's own location so it works from any machine/checkout.
% Single source of truth for where protocols read their *_parameters.m files.
% This file lives in code/src, so the repo's code/ root is one level up;
% the parameter files live under code/parameters/bpod.
this_dir  = fileparts(mfilename('fullpath'));   % code/src
code_root = fileparts(this_dir);                % Code
d = fullfile(code_root, 'parameters', 'bpod');
end
