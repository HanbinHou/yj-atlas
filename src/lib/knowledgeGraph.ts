import type { CollectionEntry } from 'astro:content';
import { getMaterialId, getMaterialNames } from './materials';

type CaseEntry = CollectionEntry<'cases'>;
type MaterialEntry = CollectionEntry<'materials'>;
type BookEntry = CollectionEntry<'books'>;

export type KnowledgeMaterialNode = {
  label: string;
  id: string;
  url?: string;
  hasPage: boolean;
};

export type KnowledgeRelatedCase = {
  id: string;
  title: string;
  architect: string;
  url: string;
  sharedMaterials: string[];
  sharedTags: string[];
  sameType: boolean;
  score: number;
};

export type KnowledgeRelatedBook = {
  id: string;
  title: string;
  author: string;
  url: string;
  sharedTags: string[];
  architectMatch: boolean;
  score: number;
};

export type CaseKnowledgeGraph = {
  center: {
    title: string;
    architect: string;
    type: string;
  };
  materials: KnowledgeMaterialNode[];
  concepts: string[];
  type: string;
  relatedCases: KnowledgeRelatedCase[];
  relatedBooks: KnowledgeRelatedBook[];
};

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function findMaterialPage(
  materialId: string,
  label: string,
  allMaterials: MaterialEntry[],
): MaterialEntry | undefined {
  const normalizedLabel = normalize(label);

  return allMaterials.find((material) => {
    const knownNames = getMaterialNames(material).map(normalize);
    return (
      getMaterialId(material) === materialId ||
      material.id === materialId ||
      knownNames.includes(normalizedLabel)
    );
  });
}

function getMaterialNodes(caseEntry: CaseEntry, allMaterials: MaterialEntry[]): KnowledgeMaterialNode[] {
  const labels = caseEntry.data.materials || [];
  const ids = caseEntry.data.materialIds || [];

  return labels.map((label, index) => {
    const materialId = ids[index] || normalize(label);
    const materialPage = findMaterialPage(materialId, label, allMaterials);

    return {
      label,
      id: materialId,
      url: materialPage ? `/materials/${materialPage.id}/` : undefined,
      hasPage: Boolean(materialPage),
    };
  });
}

function getSharedMaterials(source: CaseEntry, target: CaseEntry): string[] {
  const targetIds = new Set(target.data.materialIds || []);
  const targetNames = new Set((target.data.materials || []).map(normalize));

  return unique((source.data.materials || []).filter((label, index) => {
    const sourceId = source.data.materialIds?.[index];
    return Boolean(
      (sourceId && targetIds.has(sourceId)) ||
      targetNames.has(normalize(label)),
    );
  }));
}

function getSharedTags(source: CaseEntry, target: CaseEntry): string[] {
  const sourceTags = new Set(source.data.tags || []);
  return unique((target.data.tags || []).filter((tag) => sourceTags.has(tag)));
}

function getRelatedCases(caseEntry: CaseEntry, allCases: CaseEntry[]): KnowledgeRelatedCase[] {
  return allCases
    .filter((candidate) => candidate.id !== caseEntry.id)
    .map((candidate) => {
      const sharedMaterials = getSharedMaterials(caseEntry, candidate);
      const sharedTags = getSharedTags(caseEntry, candidate);
      const sameType = candidate.data.type === caseEntry.data.type;
      const score = sharedMaterials.length * 3 + sharedTags.length * 2 + (sameType ? 1 : 0);

      return {
        id: candidate.id,
        title: candidate.data.title,
        architect: candidate.data.architect,
        url: `/cases/${candidate.id}/`,
        sharedMaterials,
        sharedTags,
        sameType,
        score,
      };
    })
    .filter((candidate) => candidate.score > 0)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title, 'zh-CN'))
    .slice(0, 6);
}

function getRelatedBooks(caseEntry: CaseEntry, allBooks: BookEntry[]): KnowledgeRelatedBook[] {
  const caseTags = new Set(caseEntry.data.tags || []);
  const architect = caseEntry.data.architect || '';

  return allBooks
    .map((book) => {
      const sharedTags = unique((book.data.tags || []).filter((tag) => caseTags.has(tag)));
      const authorBase = book.data.author?.split('(')[0]?.trim() || '';
      const architectMatch = Boolean(
        architect &&
        authorBase &&
        (book.data.author.includes(architect) || architect.includes(authorBase)),
      );
      const score = sharedTags.length * 2 + (architectMatch ? 3 : 0);

      return {
        id: book.id,
        title: book.data.title,
        author: book.data.author,
        url: `/books/${book.id}/`,
        sharedTags,
        architectMatch,
        score,
      };
    })
    .filter((book) => book.score > 0)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title, 'zh-CN'))
    .slice(0, 4);
}

export function buildCaseKnowledgeGraph(
  caseEntry: CaseEntry,
  allCases: CaseEntry[],
  allMaterials: MaterialEntry[],
  allBooks: BookEntry[],
): CaseKnowledgeGraph {
  return {
    center: {
      title: caseEntry.data.title,
      architect: caseEntry.data.architect,
      type: caseEntry.data.type,
    },
    materials: getMaterialNodes(caseEntry, allMaterials),
    concepts: unique(caseEntry.data.tags || []).slice(0, 10),
    type: caseEntry.data.type,
    relatedCases: getRelatedCases(caseEntry, allCases),
    relatedBooks: getRelatedBooks(caseEntry, allBooks),
  };
}
