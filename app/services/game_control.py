"""State transitions for the commands hosts are allowed to use."""

from __future__ import annotations

from app.repositories.game_repository import GameRepository, GameSession


class GameStateError(RuntimeError):
    pass


class GameControlService:
    def __init__(self, games: GameRepository) -> None:
        self._games = games

    async def start_game(self, actor_id: int) -> GameSession:
        session = await self._games.transition(
            allowed_statuses=frozenset({"idle", "ended"}),
            status="registration",
            started_by=actor_id,
            ended_by=None,
            reset_round=True,
        )
        if session is None:
            raise GameStateError("Ойын қазірдің өзінде жүріп жатыр.")
        return session

    async def close_registration(self) -> GameSession:
        session = await self._games.transition(
            allowed_statuses=frozenset({"registration"}), status="active"
        )
        if session is None:
            raise GameStateError("Тіркелу ашық емес.")
        return session

    async def start_vote(self) -> GameSession:
        session = await self._games.transition(
            allowed_statuses=frozenset({"active"}), status="voting"
        )
        if session is None:
            raise GameStateError("Дауыс беруді тек белсенді ойында бастауға болады.")
        return session

    async def next_round(self) -> GameSession:
        session = await self._games.transition(
            allowed_statuses=frozenset({"active", "voting"}),
            status="active",
            advance_round=True,
        )
        if session is None:
            raise GameStateError("Келесі кезеңге өтетін белсенді ойын жоқ.")
        return session

    async def end_game(self, actor_id: int) -> GameSession:
        session = await self._games.transition(
            allowed_statuses=frozenset({"registration", "active", "voting"}),
            status="ended",
            ended_by=actor_id,
        )
        if session is None:
            raise GameStateError("Аяқтайтын белсенді ойын жоқ.")
        return session
