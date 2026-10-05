# Lambda container image for AWS Graviton (arm64). Build with:
#   docker buildx build --platform linux/arm64 -f deploy/Dockerfile -t inspectagent .
FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
COPY inspectagent ${LAMBDA_TASK_ROOT}/inspectagent
CMD ["inspectagent.api.handler"]
