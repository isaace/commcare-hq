from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex

from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Episode,
    EpisodePrescription,
    LabTest,
)

from dimagi.utils.decorators.memoized import memoized

PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
ADHERENCE_CASE_TYPE = 'adherence'
PRESCRIPTION_CASE_TYPE = 'prescription'
TEST_CASE_TYPE = 'test'


class BeneficiaryCaseFactory(object):

    def __init__(self, domain, beneficiary):
        self.domain = domain
        self.beneficiary = beneficiary

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        episode_descendants = [
            self.get_adherence_case_structure(adherence, episode_structure)
            for adherence in self._adherences
        ] + [
            self.get_prescription_case_structure(prescription, episode_structure)
            for prescription in self._prescriptions
        ]
        episode_or_descendants = episode_descendants or [episode_structure]

        tests = [
            self.get_test_case_structure(labtest, ocurrence_structure)
            for labtest in self._labtests
        ]

        return episode_or_descendants + tests

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'current_address': self.beneficiary.current_address,
                    'current_episode_type': self.beneficiary.current_episode_type,
                    'dataset': 'real',
                    'first_name': self.beneficiary.firstName,
                    'last_name': self.beneficiary.lastName,
                    'name': ' '.join([self.beneficiary.firstName, self.beneficiary.lastName]),
                    'phone_number': self.beneficiary.phoneNumber,

                    'migration_created_case': 'true',
                    'migration_created_from_record': self.beneficiary.caseId,
                }
            }
        }

        if self.beneficiary.age_entered is not None:
            kwargs['attrs']['update']['age'] = self.beneficiary.age_entered
            kwargs['attrs']['update']['age_entered'] = self.beneficiary.age_entered
        else:
            if self.beneficiary.dob is not None:
                kwargs['attrs']['update']['age'] = None # TODO - calculate from dob
            else:
                kwargs['attrs']['update']['age'] = ''
            kwargs['attrs']['update']['age_entered'] = ''

        if self.beneficiary.dob is not None:
            kwargs['attrs']['update']['dob'] = self.beneficiary.dob.date()
            kwargs['attrs']['update']['dob_known'] = 'yes'
        else:
            if self.beneficiary.age_entered is not None:
                kwargs['attrs']['update']['dob'] = None # TODO - do math
            else:
                kwargs['attrs']['update']['dob'] = ''
            kwargs['attrs']['update']['dob_known'] = 'no'

        if self.beneficiary.sex is not None:
            kwargs['attrs']['update']['sex'] = self.beneficiary.sex

        if self._episode:
            kwargs['attrs']['update']['hiv_status'] = self._episode.hiv_status
            kwargs['attrs']['update']['current_patient_type_choice'] = self._episode.current_patient_type_choice

        return CaseStructure(**kwargs)

    def get_occurrence_case_structure(self, person_structure):
        kwargs = {
            'attrs': {
                'case_type': OCCURRENCE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'name': 'Occurrence #1',

                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_episode_case_structure(self, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'adherence_schedule_id': 'schedule_mwf',
                    'name': 'Episode #1: Confirmed TB (Patient)',

                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if self._episode:
            rxStartDate = self._episode.rxStartDate.date()
            kwargs['attrs']['date_opened'] = rxStartDate
            kwargs['attrs']['update']['adherence_schedule_date_start'] = rxStartDate
            kwargs['attrs']['update']['date_of_diagnosis'] = self._episode.dateOfDiagnosis.date()
            kwargs['attrs']['update']['disease_classification'] = self._episode.disease_classification
            kwargs['attrs']['update']['treatment_initiation_date'] = rxStartDate
            kwargs['attrs']['update']['weight'] = int(self._episode.patientWeight)

            if self._episode.nikshayID:
                kwargs['attrs']['external_id'] = self._episode.nikshayID
                kwargs['attrs']['update']['nikshay_id'] = self._episode.nikshayID

            if self._episode.disease_classification == 'extra_pulmonary':
                kwargs['attrs']['update']['site_choice'] = self._episode.site_choice

        return CaseStructure(**kwargs)

    def get_adherence_case_structure(self, adherence, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': ADHERENCE_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_prescription_case_structure(self, prescription, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': PRESCRIPTION_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_test_case_structure(self, labtest, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': TEST_CASE_TYPE,
                'close': False,
                'create': True,
                'update': {
                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    @property
    @memoized
    def _episode(self):
        try:
            return Episode.objects.get(beneficiaryID=self.beneficiary)
        except Episode.DoesNotExist:
            return None

    @property
    @memoized
    def _adherences(self):
        return list(Adherence.objects.filter(beneficiaryId=self.beneficiary))

    @property
    @memoized
    def _prescriptions(self):
        return list(EpisodePrescription.objects.filter(beneficiaryId=self.beneficiary))

    @property
    @memoized
    def _labtests(self):
        if self._episode:
            return list(LabTest.objects.filter(episodeId=self._episode))
        else:
            return []
