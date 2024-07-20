FROM python:3
WORKDIR /
COPY app.py ./
COPY helper.py ./
RUN pip install --upgrade pip && pip install flask
RUN pip install requests
CMD ["python3", "app.py"]