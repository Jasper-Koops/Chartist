from rest_framework.exceptions import APIException


class NoAnalysisFoundException(APIException):
    status_code = 404
    default_detail = "No PCA analysis has been run yet."
    default_code = "no_analysis_found"
