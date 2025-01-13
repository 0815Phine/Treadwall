% Helper function to determine the correct stimulus output based on trial type
function stimOutput = GetStimOutput(trialType)
    switch trialType
        case 'C45'
            stimOutput = ['P' 1 0];
        case 'C39'
            stimOutput = ['P' 1 1];
        case 'C33'
            stimOutput = ['P' 1 2];
        case 'C27'
            stimOutput = ['P' 1 3];
        case 'L45'
            stimOutput = ['P' 1 4];
        case 'L39'
            stimOutput = ['P' 1 5];
        case 'L33'
            stimOutput = ['P' 1 6];
        case 'L27'
            stimOutput = ['P' 1 7];
        case 'R45'
            stimOutput = ['P' 1 8];
        case 'R39'
            stimOutput = ['P' 1 9];
        case 'R33'
            stimOutput = ['P' 1 10];
        case 'R27'
            stimOutput = ['P' 1 11];
        otherwise
            error('Unknown trial type: %s', trialType);
    end
end
