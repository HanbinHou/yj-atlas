import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const casesCollection = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/cases" }),
  schema: z.object({
    title: z.string(),
    architect: z.string(),
    year: z.number(),
    type: z.string(),
    materials: z.array(z.string()).default([]),
    location: z.string(),
    tags: z.array(z.string()).default([]),
    description: z.string(),
    status: z.string().optional(),
    images: z.array(z.string()).default([]),
  }),
});

const materialsCollection = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/materials" }),
  schema: z.object({
    title: z.string(),
    category: z.string(),
    subcategory: z.string().optional(),
    scenarios: z.array(z.string()).default([]),
    description: z.string(),
    properties: z.array(z.object({
      name: z.string(),
      value: z.string(),
    })).default([]),
    supplier: z.object({
      name: z.string(),
      url: z.string().optional(),
    }).optional(),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(),
  }),
});

const booksCollection = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/books" }),
  schema: z.object({
    title: z.string(),
    author: z.string(),
    year: z.number().optional(),
    category: z.string(),
    summary: z.string(),
    tags: z.array(z.string()).default([]),
    readingPath: z.enum(['beginner', 'intermediate', 'advanced']),
    coverImage: z.string().optional(),
    // unlock system
    price: z.number().optional(),
    unlockCode: z.string().optional(),
    hiddenContent: z.string().optional(),
    hiddenImage: z.string().optional(),
  }),
});

export const collections = {
  cases: casesCollection,
  materials: materialsCollection,
  books: booksCollection,
};
