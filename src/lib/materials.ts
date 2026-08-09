type MaterialEntry = {
  id: string;
  data: {
    title: string;
    canonicalId?: string;
    aliases?: string[];
  };
};

type CaseEntry = {
  data: {
    materials?: string[];
    materialIds?: string[];
  };
};

export function getMaterialId(material: MaterialEntry): string {
  return material.data.canonicalId || material.id;
}

export function getMaterialNames(material: MaterialEntry): string[] {
  return [
    material.data.title,
    material.id,
    getMaterialId(material),
    ...(material.data.aliases || []),
  ].filter(Boolean);
}

export function caseUsesMaterial(caseEntry: CaseEntry, material: MaterialEntry): boolean {
  const caseMaterialIds = caseEntry.data.materialIds || [];
  const caseMaterialNames = caseEntry.data.materials || [];
  const materialId = getMaterialId(material);

  return (
    caseMaterialIds.includes(materialId) ||
    caseMaterialIds.includes(material.id) ||
    getMaterialNames(material).some((name) => caseMaterialNames.includes(name))
  );
}
