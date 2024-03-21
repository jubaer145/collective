from canvas_workflow_kit.protocol import (
    ClinicalQualityMeasure,
    ProtocolResult,
    STATUS_DUE,
    STATUS_SATISFIED
)

from canvas_workflow_kit.constants import CHANGE_TYPE
from canvas_workflow_kit.recommendation import  InstructionRecommendation
from canvas_workflow_kit.value_set import ValueSet


class PostmenopausalState(ValueSet):
    VALUE_SET_NAME = 'Postmenopausal State' 
    ICD10CM = {'N95.0', 'N95.1'}
    
class Hysterectomy(ValueSet):
    VALUE_SET_NAME = 'Hysterectomy'
    ICD10CM = {'Z90.710'}

class PostmenopausalHormoneTherapyInstruction(ValueSet):
    VALUE_SET_NAME = 'Postmenopausal hormone replacement therapy'
    ICD10CM = {'Z79.890'}

class HormoneTherapyProtocol(ClinicalQualityMeasure):

    class Meta:

        title = 'Hormone Therapy Protocol'

        description = 'Hormone Therapy in Postmenopausal Persons who had hysterectomy'

        version = '2022-11-01v2'

        information = 'https://docs.canvasmedical.com'

        identifiers = ['CMS12345v1']

        types = ['CQM']

        compute_on_change_types = [
            CHANGE_TYPE.CONDITION,
            CHANGE_TYPE.PATIENT,
            CHANGE_TYPE.INTERVIEW
        ]

        references = [
            'Protocol Reference https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/menopausal-hormone-therapy-preventive-medication'
        ]


    def in_denominator(self):
        """
        Patients in the postmenopausal state.
        """
        return self.patient.conditions.find(PostmenopausalState)

    def in_numerator(self):
        """
        Postmenopausal patient who had hysterectomy.
        """
        return self.patient.procedures.find(Hysterectomy)

    def compute_results(self):
        result = ProtocolResult()

        if self.in_denominator(): # ifpatient is in postmenopausal state
            if self.in_numerator(): # if patient also had hysterectomy
                result.status = STATUS_SATISFIED
                result.add_narrative(
                    f'{self.patient.first_name} has been given recommendations.'
                )

                result.add_recommendation(
                    InstructionRecommendation(
                        key='RECOMMEND_DISCUSS_HORMONE_INTAKE',
                        rank=1,
                        button='Instruct',
                        patient=self.patient,
                        instruction=PostmenopausalHormoneTherapyInstruction,
                        title='Discuss ans Instruct on Hormone Intake in Postmenopausal State'
                        
                        
                        
                    )
                )
        return result
