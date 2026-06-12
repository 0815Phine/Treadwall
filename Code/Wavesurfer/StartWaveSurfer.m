function StartWaveSurfer(wsp_file, session_dir, base_name)
% Opens WaveSurfer, pre-fills output folder + filename, and starts an IPC
% timer that handles two signals from the experiment GUI:
%
%   pending_session.json  →  update filename for a new session
%   stop_wavesurfer.flag  →  stop recording, rename _00001.h5 → base_name.h5

IPC_DIR = 'C:\Users\TomBombadil\Data\ipc';

fprintf('\n=== Opening WaveSurfer ===\n');

if ~isempty(wsp_file) && exist(wsp_file, 'file')
    ws = wavesurfer(wsp_file);
else
    ws = wavesurfer();
end

% Pre-fill output folder and filename (no _ws suffix, no sweep number).
ws.DataFileLocation = session_dir;
ws.DataFileBaseName = base_name;

fprintf('WaveSurfer ready:\n');
fprintf('  Output folder : %s\n', session_dir);
fprintf('  Filename base : %s\n', base_name);
fprintf('  --> Press Record when camera and Bpod show ready\n\n');

% ── IPC: persist current session info ───────────────────────────────────────
if ~exist(IPC_DIR, 'dir'), mkdir(IPC_DIR); end
state_file = fullfile(IPC_DIR, 'current_session_ws.json');
fid = fopen(state_file, 'w');
fprintf(fid, '%s', jsonencode(struct('session_dir', session_dir, 'base_name', base_name)));
fclose(fid);

% ── IPC: start polling timer ─────────────────────────────────────────────────
t = timer('Period', 0.5, 'ExecutionMode', 'fixedRate', ...
    'TimerFcn', @(~,~) ws_ipc_check(ws, IPC_DIR));
start(t);
fprintf('IPC timer started (0.5 s poll interval).\n');

end  % StartWaveSurfer


function ws_ipc_check(ws, ipc_dir)
% Timer callback: react to signals from the GUI.
pending_file = fullfile(ipc_dir, 'pending_ws.json');
stop_flag    = fullfile(ipc_dir, 'stop_wavesurfer.flag');
state_file   = fullfile(ipc_dir, 'current_session_ws.json');

% ── New session: update filename ─────────────────────────────────────────────
if exist(pending_file, 'file')
    try
        info = jsondecode(fileread(pending_file));
        delete(pending_file);
        ws.DataFileLocation = info.session_dir;
        ws.DataFileBaseName = info.base_name;
        % Update persisted state so stop handler knows where to rename
        fid = fopen(state_file, 'w');
        fprintf(fid, '%s', jsonencode(struct('session_dir', info.session_dir, 'base_name', info.base_name)));
        fclose(fid);
        fprintf('[WaveSurfer IPC] Updated to: %s\n', info.base_name);
    catch e
        fprintf('[WaveSurfer IPC] Error reading pending session: %s\n', e.message);
    end
end

% ── Stop recording and rename sweep file ─────────────────────────────────────
if exist(stop_flag, 'file')
    try
        delete(stop_flag);

        % Capture WaveSurfer's live target before stopping (for diagnostics
        % and as a fallback if the persisted GUI state is missing).
        try
            ws_loc  = ws.DataFileLocation;
            ws_base = ws.DataFileBaseName;
        catch
            ws_loc  = '';
            ws_base = '';
        end

        % Stop recording (try both common API names)
        try
            ws.stop();
        catch
            try
                ws.record(false);
            catch
                fprintf('[WaveSurfer IPC] Could not stop WaveSurfer via API.\n');
            end
        end

        pause(2);  % let WaveSurfer finish flushing the HDF5 file

        % Intended destination = what the GUI told us this session is called.
        if exist(state_file, 'file')
            curr      = jsondecode(fileread(state_file));
            dest_dir  = curr.session_dir;
            dest_base = curr.base_name;
        else
            dest_dir  = ws_loc;
            dest_base = ws_base;
        end
        new_path = fullfile(dest_dir, [dest_base '.h5']);

        % Diagnostics: record where WaveSurfer actually wrote, so a wrong name
        % is visible in the log instead of silently lost.
        fprintf('[WaveSurfer IPC] Stop: target base=%s, location=%s\n', dest_base, ws_loc);
        listing = dir(fullfile(dest_dir, '*.h5'));
        fprintf('[WaveSurfer IPC] %d .h5 file(s) in %s\n', numel(listing), dest_dir);

        % (a) Primary: rename base_name_*.h5 (any digit count / multiple sweeps).
        files = dir(fullfile(dest_dir, [dest_base '_*.h5']));
        if ~isempty(files)
            [~, ord] = sort({files.name});
            files = files(ord);
            if numel(files) == 1
                movefile(fullfile(files(1).folder, files(1).name), new_path);
                fprintf('[WaveSurfer IPC] Renamed: %s.h5\n', dest_base);
            else
                for k = 1:numel(files)
                    movefile(fullfile(files(k).folder, files(k).name), ...
                        fullfile(dest_dir, sprintf('%s_%02d.h5', dest_base, k)));
                end
                fprintf('[WaveSurfer IPC] Renamed %d sweep files for %s\n', numel(files), dest_base);
            end
        else
            % (b) Fallback: no exact match (e.g. manual-Record name race) —
            % rename the most-recently-modified .h5 in the recording folder.
            fb_dir = dest_dir;
            fb = dir(fullfile(fb_dir, '*.h5'));
            fb = fb(~strcmpi({fb.name}, [dest_base '.h5']));   % skip already-correct name
            if isempty(fb) && ~isempty(ws_loc) && ~strcmp(ws_loc, dest_dir)
                fb_dir = ws_loc;
                fb = dir(fullfile(fb_dir, '*.h5'));
                fb = fb(~strcmpi({fb.name}, [dest_base '.h5']));
            end
            if ~isempty(fb)
                [~, newest] = max([fb.datenum]);
                src = fullfile(fb(newest).folder, fb(newest).name);
                if ~exist(dest_dir, 'dir'), mkdir(dest_dir); end
                movefile(src, new_path);
                fprintf(['[WaveSurfer IPC] No exact match for %s_*.h5; fallback ' ...
                    'renamed newest .h5 (%s) -> %s.h5\n'], dest_base, fb(newest).name, dest_base);
            else
                fprintf(['[WaveSurfer IPC] No .h5 file found to rename for %s. ' ...
                    'Was Record pressed? Check WaveSurfer output directory.\n'], dest_base);
            end
        end
    catch e
        fprintf('[WaveSurfer IPC] Error during stop/rename: %s\n', e.message);
    end
end

end  % ws_ipc_check
