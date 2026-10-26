import json

from django.test import SimpleTestCase, TestCase

from apps.floorsheet.models import Broker
from apps.floorsheet.services import broker_directory


def member(code=58, **overrides):
    return {
        "memberCode": code, "memberName": "Naasa Securities Co. Ltd.", "activeStatus": "A", "isDealer": "N",
        "membershipTypeMaster": {"membershipType": "Trading Cum Clearing Member"},
        "authorizedContactPerson": "Ram", "authorizedContactPersonNumber": "4440384",
        "memberTMSLinkMapping": {"tmsLink": "tms58.nepsetms.com.np"},
        **overrides,
    }


def profile(code="58", **overrides):
    return {
        "code": code, "name": "Naasa Securities Co. Ltd.", "website": "https://www.naasasecurities.com.np/",
        "tmsUrl": "x.naasasecurities.com.np",
        "branches": [
            {"order": 2, "name": "Birgunj", "address": "Adarsha Nagar", "contactNumber": "051-1", "email": ""},
            {"order": 1, "name": "Kathmandu", "address": "Durbarmarg,  Kathmandu", "contactNumber": "01-5970084",
             "email": "info@naasasecurities.com.np"},
        ],
        **overrides,
    }


def sharehub_page(data):
    # How the Next.js page embeds it: a JS string inside self.__next_f.push([1, "..."]).
    flight = '6:["$","$L24",null,{"initialData":' + json.dumps({"success": True, "data": data}) + "}]\n"
    return f'<script>self.__next_f.push([1,{json.dumps(flight)}])</script>'


class ParseTests(SimpleTestCase):

    def test_reads_the_embedded_broker(self):
        data = broker_directory.parse_sharehub_profile("<html>" + sharehub_page(profile()) + "</html>")
        self.assertEqual((data["code"], data["website"]), ("58", "https://www.naasasecurities.com.np/"))

    def test_page_without_broker_data(self):
        self.assertIsNone(broker_directory.parse_sharehub_profile("<html>404</html>"))

    def test_fields_merge_nepse_and_sharehub(self):
        fields = broker_directory.directory_fields(member(), profile())
        self.assertEqual(fields["website"], "https://www.naasasecurities.com.np")
        self.assertEqual(fields["tms_link"], "tms58.nepsetms.com.np")            # NEPSE wins
        self.assertEqual((fields["address"], fields["phone"]), ("Durbarmarg, Kathmandu", "01-5970084"))  # head office
        self.assertEqual([b["name"] for b in fields["branches"]], ["Kathmandu", "Birgunj"])
        self.assertTrue(fields["is_active"])

    def test_without_sharehub_profile_uses_nepse_phone(self):
        fields = broker_directory.directory_fields(member(activeStatus="SUSPEND"), None)
        self.assertEqual((fields["website"], fields["phone"], fields["is_active"]), ("", "4440384", False))


class SyncTests(TestCase):

    def test_creates_updates_and_keeps_admin_website(self):
        Broker.objects.create(broker_code="58", name="Old name", logo="58.png")
        Broker.objects.create(broker_code="55", broker_no=55, name="Bhrikuti", website="https://bhrikutistock.com")
        Broker.objects.create(broker_code="2", broker_no=2, name="Gone")

        counts = broker_directory.sync_broker_directory(
            [member(), member(55, memberName="Bhrikuti Stock Broking Co. Pvt. Ltd."), member(7, memberName="J.F. Securities")],
            {"58": profile()},
        )
        self.assertEqual(counts, {"created": 1, "updated": 2, "with_website": 1, "delisted": 1})
        naasa = Broker.objects.get(broker_code="58")
        self.assertEqual((naasa.broker_no, naasa.name, naasa.logo, naasa.website),
                         (58, "Naasa Securities Co. Ltd.", "58.png", "https://www.naasasecurities.com.np"))
        self.assertEqual(Broker.objects.get(broker_no=55).website, "https://bhrikutistock.com")   # no page: kept
        self.assertFalse(Broker.objects.get(broker_no=2).is_active)
        self.assertEqual(Broker.objects.get(broker_no=7).membership_type, "Trading Cum Clearing Member")
