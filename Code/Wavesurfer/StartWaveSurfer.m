function StartWaveSurfer(wsp_file, session_dir, base_name)
% Opens WaveSurfer, loads the protocol, and pre-fills output folder + filename.
% Called from StartSession.ps1 in a dedicated MATLAB instance.
% The user only needs to press Record when camera and Bpod show ready.

fprintf('\n=== Opening WaveSurfer ===\n');

if ~isempty(wsp_file) && exist(wsp_file, 'file')
    ws = wavesurfer(wsp_file);
else
    ws = wavesurfer();
end

% Pre-fill output folder and filename.
% Property names differ between WaveSurfer versions — try common variants.
configured = false;
ws.DataFileLocation = session_dir;
ws.DataFileBaseName = [base_name '_ws'];

fprintf('WaveSurfer ready:\n');
fprintf('  Output folder : %s\n', session_dir);
fprintf('  Filename base : %s_ws\n', base_name);

fprintf('  --> Press Record when camera and Bpod show ready\n\n');

end
