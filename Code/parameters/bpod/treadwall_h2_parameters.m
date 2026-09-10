%% Parameters for Treadwall_Habituation_2 (full travel length)
% Loaded by Treadwall_Habituation_2.m via treadwall_params_dir().

% -------- Behaviour --------
STIM_DUR = 110;                                        % s, stimulus duration
ITI_DUR = 15;                                          % s, inter-trial interval
WAVEFORMS = {0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5};  % V per distance step
INIT_SCALING_FACTOR = 1;                               % initial wall-sync scaling factor
WAVE_BUFFER = 5;                                       % s, extra waveform length added beyond stimDur

% -------- Hardware --------
WAVEPLAYER_TRIGGER_MODE = 'Master';                    % Bpod WavePlayer trigger mode
STOP_CAMERA_DELAY = 1;                                 % s, BNC1 pulse hold that stops the camera
