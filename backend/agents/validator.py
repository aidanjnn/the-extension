import os
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low

from agents.models import ValidateRequest, ValidateResponse
from utils.extension_validator import validate_extension

VALIDATOR_SEED = os.getenv("VALIDATOR_AGENT_SEED", "validator-default-seed")

validator = Agent(
    name="the-extension-validator",
    seed=VALIDATOR_SEED,
    port=8003,
    endpoint=["http://localhost:8003/submit"],
)

fund_agent_if_low(validator.wallet.address())


@validator.on_message(model=ValidateRequest)
async def handle_validate_request(ctx: Context, sender: str, msg: ValidateRequest):
    ctx.logger.info(f"Validator received {len(msg.files)} files")
    result = validate_extension(msg.files)
    ctx.logger.info(f"Validation result: valid={result.valid}, errors={len(result.errors)}")
    await ctx.send(
        sender,
        ValidateResponse(
            valid=result.valid,
            errors=result.errors,
            warnings=result.warnings,
        ),
    )
