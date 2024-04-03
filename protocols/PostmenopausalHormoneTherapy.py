from canvas_workflow_kit.protocol import (
    ClinicalQualityMeasure,
    ProtocolResult,
    STATUS_DUE,
    STATUS_SATISFIED
)

from canvas_workflow_kit.constants import CHANGE_TYPE
from canvas_workflow_kit.recommendation import  InstructionRecommendation, PrescribeRecommendation
from canvas_workflow_kit.value_set import ValueSet


class PostmenopausalState(ValueSet):
    VALUE_SET_NAME = 'Postmenopausal State' 
    ICD10CM = {'N95.0', 'N95.1'}
    
class Hysterectomy(ValueSet):
    VALUE_SET_NAME = 'Hysterectomy'
    ICD10CM = {'Z90.710'}
    SNOMEDCT = {'236886002'}

class PostmenopausalHormoneTherapyInstruction(ValueSet):
    VALUE_SET_NAME = 'Postmenopausal hormone replacement therapy'
    ICD10CM = {'Z79.890'}

class EstrogenTherapy(ValueSet):
    VALUE_SET_NAME = 'Estrogen therapy'
    LOINC = {'2254-1'}


class ProgestinTherapy(ValueSet):
    VALUE_SET_NAME = 'Progestin therapy'
    LOINC = {'2839-9'}
    
class EstrogenAndProgestinTherapy(ValueSet):
    VALUE_SET_NAME = 'Progestin therapy'
    LOINC = {'2839-9', '2254-1'}
    
    


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
        If patient is in the postmenopausal state.
        """
        return len(self.patient.conditions.find(PostmenopausalState)) > 0

    def in_numerator(self):
        """
        Menopausal hormone therapy refers to the use of combined estrogen and progestin in persons with an intact uterus, or estrogen
        alone in persons who have had a hysterectomy, taken at or after
        the time of menopause.
        """
        progestin_therapy = len(self.patient.medications.find(ProgestinTherapy)) > 0
        estrogen_therapy = len(self.patient.medications.find(EstrogenTherapy)) > 0    
        
        # if patient has hysterectomy
        if len(self.patient.conditions.find(Hysterectomy)) > 0:
            # patient should have only estrogen therapy
            return estrogen_therapy and not progestin_therapy
        # otherwise patient should have both estrogen and progestin therapy
        return estrogen_therapy and progestin_therapy
            
     
     
     
            

    def compute_results(self):
        result = ProtocolResult()

        if self.in_denominator(): # if patient is in postmenopausal state
            if len(self.patient.conditions.find(Hysterectomy)) > 0: # if patient had hysterectomy 
                # if patient had hysterectomy but not having only estrogen therapy   
                if not self.in_numerator():
                    result.status = STATUS_DUE
                    result.add_recommendation(
                        PrescribeRecommendation(
                            key='RECOMMEND_ESTROGEN_THERAPY',
                                    rank=1,
                                    button='Prescribe',
                                    patient=self.patient,
                                    prescription=EstrogenTherapy,
                                    title='Recommendation of Estrogen Therapy.',
                                    context={}
                                )
                    )
            else: # if patient did not have hysterectomy   
                # patient not having both estrogen and progestin therapy
                if not self.in_numerator():      
                    result.status = STATUS_DUE
                    result.add_recommendation(
                        PrescribeRecommendation(
                            key='RECOMMEND_ESTROGEN_AND_PROGESTIN_THERAPY',
                                    rank=1,
                                    button='Prescribe',
                                    patient=self.patient,
                                    prescription=EstrogenAndProgestinTherapy,
                                    title='Recommendation of Estrogen and Progestin Therapy.',
                                    context={}
                                )
                    )
                
        return result
