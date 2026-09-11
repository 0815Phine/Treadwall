function d = gui_ipcdir()
% Canonical IPC directory shared by the Treadwall GUI and every protocol.
% Sourced from the central config (treadwall_config.json) so the Python GUI and
% all MATLAB scripts share one value (a past IPC_DIR mismatch broke all IPC).
d = treadwall_config().paths.ipc_dir;
end
