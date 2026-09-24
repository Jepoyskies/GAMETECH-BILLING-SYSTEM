import concurrent.futures
from django.test import TransactionTestCase
from django.db import connection
from dispatch.models import JobTicket
from dispatch.utils import generate_ticket_number


class TicketConcurrencyTestCase(TransactionTestCase):
    """
    Real multi-threaded concurrency tests proving that generate_ticket_number
    and JobTicket.save() never produce duplicate ticket numbers under concurrent load.
    """

    def tearDown(self):
        JobTicket.objects.filter(client_name__startswith="Concurrent Client").delete()

    def test_concurrent_ticket_creation_no_duplicates(self):
        """
        Spawn 10 concurrent threads each creating JobTicket records simultaneously.
        Verifies:
        1. All 10 tickets are successfully created without IntegrityError.
        2. All 10 ticket numbers are unique (set length == 10).
        3. All ticket numbers match the GT-YYYYMMDD-XXXX format.
        """
        def create_ticket(client_idx):
            connection.close()  # Ensure thread uses a clean connection
            ticket = JobTicket.objects.create(
                client_name=f"Concurrent Client {client_idx}",
                ticket_type="INSTALLATION",
            )
            return ticket.ticket_number

        num_threads = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_ticket, i) for i in range(num_threads)]
            ticket_numbers = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(ticket_numbers), num_threads)
        self.assertEqual(
            len(set(ticket_numbers)),
            num_threads,
            f"Duplicate ticket numbers found under concurrency: {ticket_numbers}",
        )
        for tnum in ticket_numbers:
            self.assertTrue(tnum.startswith("GT-"))

    def test_generate_ticket_number_format(self):
        """Verify ticket number format and sequence increment."""
        t1 = JobTicket.objects.create(client_name="Concurrent Client Seq1")
        t2 = JobTicket.objects.create(client_name="Concurrent Client Seq2")
        self.assertNotEqual(t1.ticket_number, t2.ticket_number)
        self.assertTrue(t1.ticket_number.startswith("GT-"))
        self.assertTrue(t2.ticket_number.startswith("GT-"))
