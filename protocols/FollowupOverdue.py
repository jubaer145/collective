import datetime

from enum import Enum
from typing import Optional

import arrow

from canvas_workflow_kit.patient_recordset import (
    AppointmentRecordSet,
    InterviewRecordSet,
    MessageRecordSet,
    UpcomingAppointmentRecordSet,
)
from canvas_workflow_kit.protocol import (
    CHANGE_TYPE,
    STATUS_DUE,
    STATUS_NOT_APPLICABLE,
    STATUS_SATISFIED,
    ClinicalQualityMeasure,
    ProtocolResult,
)
from canvas_workflow_kit.value_set import ValueSet

# Replace with the IDs of the questionnaires you want to use
PHONE_CALL_DISPOSITION_QUESTIONNAIRE_ID = 'QUES_PHONE_01'
RISK_STRATIFICATION_QUESTIONNAIRE_ID = 'DUO_QUES_RISK_STRAT_01'
RISK_STRATIFICATION_QUESTION_ID = 'DUO_QUES_RISK_STRAT_02'

# Replace with the timezone of your clinic
NOW = arrow.now(tz='America/Phoenix')

# -- each of these is the window + 10% (33 days, 66 days, 198 days)
SIX_MONTHS_WINDOW = datetime.timedelta(days=198)
TWO_MONTH_WINDOW = datetime.timedelta(days=66)
NEXT_MONTH_WINDOW = datetime.timedelta(days=33)

LONG_TIME_AGO = NOW.shift(years=-10)

# Replace with the default risk stratification
DEFAULT_RISK = 'Low'

# Replace with the risk window codes for each risk stratification window
RISK_WINDOWS = {
    'Low': SIX_MONTHS_WINDOW,
    'Medium': SIX_MONTHS_WINDOW,
    'High Risk': TWO_MONTH_WINDOW,
    'High Risk - Unstable': NEXT_MONTH_WINDOW,
}


class PhoneResponses(Enum):
    REACHED = 'QUES_PHONE_03'
    REACHED_NOT_INTERESTED = 'QUES_PHONE_04'
    NO_ANSWER_MESSAGE = 'QUES_PHONE_05'
    NO_ANSWER_NO_MESSAGE = 'QUES_PHONE_06'
    CALL_BACK_REQUESTED = 'QUES_PHONE_08'
    CALL_TO_PATIENT = 'QUES_PHONE_10'
    CALL_TO_OTHER = 'QUES_PHONE_11'
    FREE_TEXT = 'QUES_PHONE_16'


class PhoneQuestions(Enum):
    DISPOSITION = 'QUES_PHONE_01'
    CALL_TO_FROM = 'QUES_PHONE_02'
    COMMENTS = 'QUES_PHONE_16'


class PhoneCallDispositionQuestionnaire(ValueSet):
    VALUE_SET_NAME = 'Phone Call Disposition Questionnaire'
    INTERNAL = {PHONE_CALL_DISPOSITION_QUESTIONNAIRE_ID}


class RiskStratificationQuestionnaire(ValueSet):
    VALUE_SET_NAME = 'Risk Stratification Questionnaire'
    INTERNAL = {RISK_STRATIFICATION_QUESTIONNAIRE_ID}


class FollowupOverdue(ClinicalQualityMeasure):
    class Meta:
        title = 'Follow-ups: Follow-up Overdue'
        description = ()
        version = '1.0.0'
        information = 'https://canvasmedical.com/gallery'  # Replace with the link to your protocol.
        identifiers = []
        types = ['DUO']
        compute_on_change_types = [CHANGE_TYPE.INTERVIEW, CHANGE_TYPE.APPOINTMENT]
        references = []

    def _get_risk_stratification(self, latest_date: arrow.Arrow = LONG_TIME_AGO):
        '''
        Take a set of interviews for a patient and determine the most recent
        risk stratification.

        Args:
            latest_date (arrow.Arrow): The latest date to consider for risk stratification.
                Defaults to LONG_TIME_AGO.

        Returns:
            str: The code representing the most recent risk stratification,
                or DEFAULT_RISK if no risk stratification is found.
        '''
        latest_risk_questionnaire = self.patient.interviews.find(
            RiskStratificationQuestionnaire
        ).last()

        if (
            latest_risk_questionnaire
            and arrow.get(latest_risk_questionnaire['noteTimestamp']) > latest_date
        ):
            return next(
                (
                    response['value']
                    for response in latest_risk_questionnaire['responses']
                    if response['code'] == RISK_STRATIFICATION_QUESTION_ID
                ),
                DEFAULT_RISK,
            )

        return DEFAULT_RISK

    def _get_risk_stratification_period(self) -> datetime.timedelta:
        '''
        Returns the risk stratification period based on the risk stratification level.

        If the risk stratification level is not found in the RISK_WINDOWS dictionary,
        the default period of SIX_MONTHS_WINDOW is returned.

        Returns:
            datetime.timedelta: The risk stratification period.
        '''
        return RISK_WINDOWS.get(self._get_risk_stratification(), SIX_MONTHS_WINDOW)

    def _is_after_risk_period(self, date: arrow.Arrow) -> bool:
        '''
        Check if the given date is after the upcoming risk stratification period.

        Args:
            date (arrow.Arrow): The date to compare.

        Returns:
            bool: True if the date is after the risk stratification period, False otherwise.
        '''
        return date > NOW + self._get_risk_stratification_period()

    def _is_before_risk_period(self, date: arrow.Arrow) -> bool:
        '''
        Check if the given date is before the upcoming risk period.

        Args:
            date (arrow.Arrow): the date to check.

        Returns:
            bool: true if the date is before the risk period, false otherwise.
        '''
        return date < NOW + self._get_risk_stratification_period()

    def _get_phone_calls_to_patient(self) -> InterviewRecordSet:
        '''Get all phone calls made to this patient.

        Returns:
            InterviewRecordSet: A set of phone call records made to the patient.
        '''
        phone_calls = self.patient.interviews.find(PhoneCallDispositionQuestionnaire).filter(
            status='AC'
        )
        return InterviewRecordSet(
            [
                phone_call
                for phone_call in phone_calls
                if any(
                    PhoneResponses(response['code']) == PhoneResponses.CALL_TO_PATIENT
                    for response in phone_call['responses']
                )
            ]
        )

    def _get_messages_to_patient_after(
        self, start_time: arrow.Arrow = LONG_TIME_AGO
    ) -> MessageRecordSet:
        '''Get all messages to this patient from staff after a certain time.

        Args:
            start_time (arrow.Arrow, optional): The start time to filter messages.
                Defaults to LONG_TIME_AGO.

        Returns:
            MessageRecordSet: A set of messages sent to the patient by staff
                after the specified start time.
        '''
        return MessageRecordSet(
            [
                message
                for message in self.patient.messages
                if any(sender['type'] == 'Staff' for sender in message['sender'])
                and arrow.get(message['created']) > start_time
            ]
        )

    def _get_past_appointments(self) -> AppointmentRecordSet:
        '''Returns a filtered list of past appointments for the patient.

        This method filters the list of appointments for the patient and returns
        only the appointments that have a state history indicating a check-in.

        Returns:
            AppointmentRecordSet: A filtered list of past appointments.
        '''
        return AppointmentRecordSet(
            [
                appointment
                for appointment in self.patient.appointments
                if any(state['state'] == 'CVD' for state in appointment['stateHistory'])
            ]
        )

    def _get_most_recent_appointment(self) -> Optional[arrow.Arrow]:
        '''Returns the most recent appointment date and time.

        This method retrieves the past appointments and finds the most recent appointment
        based on the 'created' timestamp in the appointment's state history.

        Returns:
            arrow.Arrow: The most recent appointment date and time.
        '''
        appointments = self._get_past_appointments()
        return max(
            (
                arrow.get(state['created'])
                for appointment in appointments.records
                for state in appointment['stateHistory']
                if state['state'] == 'CVD'
            ),
            default=None,
        )

    def _get_upcoming_appointments(self) -> UpcomingAppointmentRecordSet:
        '''Get all uncancelled upcoming appointments for this patient.

        Returns:
            UpcomingAppointmentRecordSet: A record set containing all uncancelled
                upcoming appointments.
        '''
        return UpcomingAppointmentRecordSet(
            [
                appointment
                for appointment in self.patient.upcoming_appointments
                if appointment['status'] != 'cancelled'
            ]
        )

    def in_denominator(self) -> bool:
        '''
        Check for patients who:
            - have no follow-up appointment within the risk stratification period
            - have not been contacted since their last appointment.

        Returns:
            bool: True if the patient satisfies the above condition, False otherwise.
        '''
        no_follow_up_appointment = (
            not any(
                self._is_before_risk_period(arrow.get(appointment['startTime']))
                for appointment in self.patient.upcoming_appointments
            )
            if bool(self.patient.upcoming_appointments)
            else True
        )
        most_recent_appointment_time = self._get_most_recent_appointment()
        messages_after_recent = (
            self._get_messages_to_patient_after(most_recent_appointment_time)
            if most_recent_appointment_time
            else False
        )
        phone_calls_after_recent = (
            self._get_phone_calls_to_patient().after(most_recent_appointment_time)
            if most_recent_appointment_time and self._get_phone_calls_to_patient()
            else False
        )
        no_recent_contact = not (messages_after_recent or phone_calls_after_recent)
        return no_follow_up_appointment and no_recent_contact

    def in_numerator(self) -> bool:
        '''Check for patients who have been called in the past week.

        Returns:
            bool: True if the patient has been called in the past week, False otherwise.
        '''
        return bool(self._get_phone_calls_to_patient().after(NOW.shift(weeks=-1)))

    def compute_results(self) -> ProtocolResult:
        result = ProtocolResult()
        if self.in_denominator():
            if self.in_numerator():
                result.status = STATUS_SATISFIED
                result.add_narrative('Patient has been contacted in the past week.')
            else:
                result.due_in = -1
                result.status = STATUS_DUE
                result.add_narrative(
                    'Patient has no follow-up appointment within their risk stratification '
                    'period and has not been contacted over the past period.'
                )
        else:
            result.status = STATUS_NOT_APPLICABLE
            result.add_narrative(
                'Patient has an appointment within their risk period or has been contacted.'
            )

        return result
