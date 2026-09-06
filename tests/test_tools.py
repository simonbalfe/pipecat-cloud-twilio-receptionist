import unittest
from typing import cast

from pipecat.pipeline.worker import PipelineWorker

from receptionist.email import EmailSender
from receptionist.tools import CallTools, Enquiry, SurveyorMessage


class CallToolsTest(unittest.TestCase):
    def test_enquiry_tool_uses_enquiry_fields(self) -> None:
        tools = CallTools(
            email=EmailSender("test", "0" * 32, "from@example.com", "to@example.com"),
            caller_phone="+447700900000",
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


if __name__ == "__main__":
    unittest.main()
