# Holiday Monitoring

This is an application used to monitor holiday price changes.

## Tech Stack

Project is created with:

- Python 3.11
- Flask 2.3.2
- bcrypt, requests, beautifulsoup4, APScheduler
- Docker
- Docker 3.11-slim-bullseye Debian image
- HTML
- CSS - Materialize Framework

## Run Locally

Clone the project

```bash
  git clone https://github.com/teh42eem00/Holiday_Monitor
```

Go to the project directory

```bash
  cd Holiday_Monitor
```

Install docker according to your operating system

https://docs.docker.com/engine/install/

Build docker image

```bash
  docker build -t holiday_monitor .
```

Start the docker image

```bash
  docker run -p 5001:5001 --name holiday_monitor -d holiday_monitor
```

That's it, application should listen on port 5000 of Docker host IP address.



## Authors

- [@teh42eem00](https://www.github.com/teh42eem00)