function stop_estop_timer(t)
% Safely stop and delete the emergency-stop timer on any exit path
% (idempotent — guards against an already-deleted timer).
try
    if isvalid(t)
        stop(t);
        delete(t);
    end
catch
end
end
