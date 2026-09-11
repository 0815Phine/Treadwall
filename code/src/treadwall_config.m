function cfg = treadwall_config()
% Rig configuration (paths + hardware) shared by the Treadwall GUI (Python) and
% every MATLAB protocol/helper. Single source of truth: Code/parameters/treadwall_config.json.
% Returns the decoded struct with fields .paths, .rspace, .bpod, .cameras.
% The file is resolved relative to this helper's own location (Code/src), so
% it works from any machine/checkout. Read fresh each call (tiny file) so edits are
% picked up without restarting MATLAB across the multi-session loop.
this_dir  = fileparts(mfilename('fullpath'));            % Code/src
code_root = fileparts(this_dir);                         % Code
cfg_file  = fullfile(code_root, 'parameters', 'treadwall_config.json');
cfg = jsondecode(fileread(cfg_file));
end
