.PHONY: help build up down restart logs stop start clean shell

# Переменные
COMPOSE = docker-compose
DOCKER = docker

help: ## Показать справку по командам
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образ
	$(COMPOSE) build

up: ## Запустить контейнер в фоновом режиме
	$(COMPOSE) up -d

down: ## Остановить и удалить контейнер
	$(COMPOSE) down

restart: ## Перезапустить контейнер
	$(COMPOSE) restart

logs: ## Показать логи контейнера
	$(COMPOSE) logs -f

stop: ## Остановить контейнер
	$(COMPOSE) stop

start: ## Запустить остановленный контейнер
	$(COMPOSE) start

clean: ## Остановить контейнер и удалить образ
	$(COMPOSE) down --rmi local

shell: ## Открыть shell в контейнере
	$(DOCKER) exec -it aidhelper-bot /bin/bash

status: ## Показать статус контейнера
	$(COMPOSE) ps

rebuild: ## Пересобрать образ и перезапустить контейнер
	$(COMPOSE) up -d --build

# Команда по умолчанию
.DEFAULT_GOAL := help
