from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ==========================================
# 1. TARGET MODELS (BioStudies JSON)
# ==========================================


class BioAttribute(BaseModel):
    name: str
    value: Optional[str] = None


class BioFile(BaseModel):
    path: str
    size: Optional[int] = None
    type: str = "file"
    attributes: List[BioAttribute] = []


class BioSection(BaseModel):
    type: str
    accNo: Optional[str] = None
    attributes: List[BioAttribute] = []
    subsections: List["BioSection"] = []
    files: List[BioFile] = []


class BioStudiesSubmission(BaseModel):
    accNo: str
    attributes: List[BioAttribute] = []
    section: BioSection


# Enable recursive reference resolution for Pydantic V2
BioSection.model_rebuild()

# ==========================================
# 2. SOURCE MODELS (ISA-JSON)
# ==========================================


class IsaComment(BaseModel):
    name: str
    value: Optional[str] = None


class IsaOntology(BaseModel):
    annotationValue: str
    termSource: Optional[str] = None


class IsaPerson(BaseModel):
    firstName: str
    lastName: str
    midInitials: Optional[str] = None
    email: Optional[str] = None
    affiliation: Optional[str] = None
    roles: List[IsaOntology] = []


class IsaDataFile(BaseModel):
    filename: str
    label: Optional[str] = None
    type: Optional[str] = None
    comments: List[IsaComment] = []


class IsaAssay(BaseModel):
    filename: str
    measurementType: Optional[IsaOntology] = None
    technologyType: Optional[IsaOntology] = None
    dataFiles: List[IsaDataFile] = []


class IsaSource(BaseModel):
    name: str
    characteristics: List[Dict[str, Any]] = []


class IsaSample(BaseModel):
    name: str
    derivesFrom: List[str] = []


class IsaMaterials(BaseModel):
    sources: List[IsaSource] = []
    samples: List[IsaSample] = []


class IsaStudy(BaseModel):
    identifier: str
    title: str
    description: Optional[str] = None
    submissionDate: Optional[str] = None
    publicReleaseDate: Optional[str] = None
    filename: str
    contacts: List[IsaPerson] = []
    materials: Optional[IsaMaterials] = None
    assays: List[IsaAssay] = []


class IsaInvestigation(BaseModel):
    identifier: str
    title: str
    description: Optional[str] = None
    submissionDate: Optional[str] = None
    publicReleaseDate: Optional[str] = None
    contacts: List[IsaPerson] = []
    studies: List[IsaStudy] = []

    def to_biostudies(self) -> BioStudiesSubmission:
        """
        Transforms ISA-JSON to BioStudies JSON structure.
        Assumes 1 Investigation -> 1 Submission.
        """

        # 1. Create Root Attributes (Title, Description, Dates)
        root_attrs = [
            BioAttribute(name="Title", value=self.title),
            BioAttribute(name="Description", value=self.description),
            BioAttribute(name="SubmissionDate", value=self.submissionDate),
            BioAttribute(name="PublicReleaseDate", value=self.publicReleaseDate),
        ]

        # 2. Process Contacts (Investigation Level) -> Authors
        root_subsections = []
        for contact in self.contacts:
            author_attrs = [
                BioAttribute(
                    name="Name", value=f"{contact.firstName} {contact.lastName}"
                ),
                BioAttribute(name="Email", value=contact.email),
                BioAttribute(name="Organization", value=contact.affiliation),
                BioAttribute(
                    name="Role",
                    value=contact.roles[0].annotationValue if contact.roles else None,
                ),
            ]
            # Filter out None values
            author_attrs = [a for a in author_attrs if a.value]
            root_subsections.append(BioSection(type="Author", attributes=author_attrs))

        # 3. Process Study (Main Section)
        # BioStudies usually centers around one Study. We take the first one.
        if not self.studies:
            raise ValueError("ISA JSON must contain at least one study.")

        study = self.studies[0]

        study_attrs = [
            BioAttribute(name="Title", value=study.title),
            BioAttribute(name="Description", value=study.description),
            BioAttribute(name="Study Identifier", value=study.identifier),
        ]

        # 4. Process Materials (Samples) -> Biosample Subsections
        study_subsections = []
        if study.materials:
            for sample in study.materials.samples:
                sample_attrs = [BioAttribute(name="Sample Name", value=sample.name)]
                if sample.derivesFrom:
                    sample_attrs.append(
                        BioAttribute(name="Derives From", value=sample.derivesFrom[0])
                    )

                study_subsections.append(
                    BioSection(
                        type="Biosample", accNo=sample.name, attributes=sample_attrs
                    )
                )

        # 5. Process Assays -> Files
        # Extract all files from all assays and attach to the Study Section
        study_files = []
        for assay in study.assays:
            for f in assay.dataFiles:
                file_attrs = [BioAttribute(name="Description", value=f.label)]
                if f.type:
                    file_attrs.append(BioAttribute(name="Type", value=f.type))

                study_files.append(BioFile(path=f.filename, attributes=file_attrs))

        # 6. Construct Final Object
        main_section = BioSection(
            type="Study",
            accNo=study.identifier,
            attributes=[a for a in study_attrs if a.value],
            subsections=study_subsections,
            files=study_files,
        )

        # Merge investigation contacts into main section if needed, or keep at root.
        # Here we attach investigation authors to the root submission,
        # but typically BioStudies expects authors in the main section.
        # Appending root authors to the main section for better compatibility:
        main_section.subsections.extend(root_subsections)

        return BioStudiesSubmission(
            accNo=self.identifier,
            attributes=[a for a in root_attrs if a.value],
            section=main_section,
        )


mock_isa_data = {
    "identifier": "INV-101",
    "title": "Investigation Title",
    "description": "Investigation Description",
    "submissionDate": "2023-01-01",
    "contacts": [
        {
            "firstName": "John",
            "lastName": "Doe",
            "affiliation": "Lab A",
            "email": "john@example.com",
        }
    ],
    "studies": [
        {
            "identifier": "STU-101",
            "title": "Study Title",
            "filename": "s_study.txt",
            "materials": {
                "samples": [{"name": "Sample-1", "derivesFrom": ["Source-1"]}]
            },
            "assays": [
                {
                    "filename": "a_assay.txt",
                    "dataFiles": [
                        {
                            "filename": "raw_data.fastq",
                            "label": "Raw Reads",
                            "type": "fastq",
                        }
                    ],
                }
            ],
        }
    ],
}


# ==========================================
# 3. EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
    import json

    # 1. Validate Source
    isa_model = IsaInvestigation(**mock_isa_data)

    # 2. Transform to Target
    biostudies_model = isa_model.to_biostudies()

    # 3. Output
    print(json.dumps(biostudies_model.model_dump(exclude_none=True), indent=2))
