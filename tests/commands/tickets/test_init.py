from src.commands.tickets import TicketsCog


def test_ticket_group_is_guild_only():
    assert TicketsCog.ticket.guild_only is True
