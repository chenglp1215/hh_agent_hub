from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agents" ADD COLUMN "supervisor_prompt_supplement" TEXT;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agents" DROP COLUMN "supervisor_prompt_supplement";
    """
