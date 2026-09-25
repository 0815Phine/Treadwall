%% Parameters for treadwall_baseline (camera + 2P only, no lateral wall movement)
% Loaded by treadwall_baseline.m via treadwall_paramsdir().

% -------- Behaviour --------
SESSION_DUR = 1200;          % s, run duration (ExperimentRunning state)
INIT_SCALING_FACTOR = 1;     % initial wall-sync scaling factor (fixed; one-trial session)
N_ACTIVE_CHAN = 1;
ANALOG_THRESHOLDS = 4.0;     % V, zone-transition thresholds (AnalogIn ch 1)
ANALOG_RESET_VOLTAGES = 3.2; % V, threshold reset voltages (AnalogIn ch 1)