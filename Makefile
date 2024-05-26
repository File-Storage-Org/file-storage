.PHONY: migrate
migrate:
	@read -p "Enter migration message: " message; \
    echo "Generating migration script"; \
    alembic revision --autogenerate -m "$$message"

.PHONY: upgrade
upgrade:
	@echo "Upgrading database"
	alembic upgrade head

.PHONY: downgrade
downgrade:
	@echo "Downgrading database"
	alembic downgrade -1

.PHONY: revision
revision:
	@echo "Generating blank revision"
	alembic revision
