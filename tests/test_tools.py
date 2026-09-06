import unittest
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from pipecat.pipeline.worker import PipelineWorker
from pipecat.services.llm_service import FunctionCallParams

from receptionist.email import EmailSender
from receptionist.tools import CallTools, Enquiry, SurveyorMessage


class CallToolsTest(unittest.TestCase):
    def test_enquiry_tool_uses_enquiry_fields(self) -> None:
        tools = CallTools(
            email=EmailSender("test", "0" * 32, "from@example.com", "to@example.com"),
            caller_phone="withheld",
            worker=cast(PipelineWorker, object()),
        ).schema()
        enquiry_tool = next(
            tool for tool in tools.standard_tools if tool.name == "submit_property_enquiry"
        )
        self.assertEqual(set(enquiry_tool.properties), set(Enquiry.model_fields))
        self.assertEqual(set(enquiry_tool.required), set(Enquiry.model_fields))

        surveyor_tool = next(
            tool for tool in tools.standard_tools if tool.name == "notify_surveyor_call"
        )
        self.assertEqual(set(surveyor_tool.properties), set(SurveyorMessage.model_fields))
        self.assertEqual(set(surveyor_tool.required), set(SurveyorMessage.model_fields))

    def test_normalizes_spoken_postcode(self) -> None:
        enquiry = Enquiry.model_validate(
            {
                "property_type": "house",
                "service": "survey",
                "address": "Example address",
                "postcode": "A B one two C D",
            }
        )
        self.assertEqual(enquiry.postcode, "AB1 2CD")

    def test_rejects_ambiguous_postcode(self) -> None:
        with self.assertRaises(ValueError):
            Enquiry.model_validate(
                {
                    "property_type": "house",
                    "service": "survey",
                    "address": "Example address",
                    "postcode": "A B one two three D",
                }
            )


class CallToolsStageTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_only_one_email_per_call(self) -> None:
        sender = EmailSender("test", "0" * 32, "from@example.com", "to@example.com")
        tools = CallTools(
            email=sender,
            caller_phone="withheld",
            worker=cast(PipelineWorker, object()),
        )
        callback = AsyncMock()
        params = cast(
            FunctionCallParams,
            MagicMock(arguments={"message": "Anonymous message"}, result_callback=callback),
        )

        with patch.object(EmailSender, "send", new=AsyncMock()) as send:
            await tools.notify_surveyor_call(params)
            await tools.notify_surveyor_call(params)

        send.assert_awaited_once()
        callback.assert_awaited_with({"status": "already_sent"})


if __name__ == "__main__":
    unittest.main()
