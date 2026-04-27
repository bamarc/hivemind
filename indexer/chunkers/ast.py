from typing import List, Dict, Any, Optional
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_go as tsgo
import tree_sitter_typescript as tstypescript
import tree_sitter_yaml as tsyaml
import tree_sitter_hcl as tshcl
from .base import ChunkingStrategy, Chunk
import os

class ASTChunker(ChunkingStrategy):
    def __init__(self, chunk_lines: int = 50, overlap_lines: int = 5):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines
        
        # Initialize parsers
        self.languages = {
            ".py": Language(tspython.language()),
            ".go": Language(tsgo.language()),
            ".ts": Language(tstypescript.language_typescript()),
            ".tsx": Language(tstypescript.language_tsx()),
            ".yaml": Language(tsyaml.language()),
            ".yml": Language(tsyaml.language()),
            ".tf": Language(tshcl.language())
        }
        self.parser = Parser()

    def _get_node_name(self, node) -> Optional[str]:
        """Extract a human-readable name for a definition node."""
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "name"):
                return child.text.decode("utf8")
        return None

    def _create_chunks_from_text(self, text: str, filepath: str, start_line: int, base_idx: int, metadata: Dict[str, Any]) -> List[Chunk]:
        """Split a block of text into smaller chunks if it exceeds chunk_lines."""
        lines = text.splitlines()
        if len(lines) <= self.chunk_lines:
            return [Chunk(
                content=text,
                filepath=filepath,
                chunk_index=base_idx,
                line_start=start_line,
                line_end=start_line + len(lines) - 1,
                metadata=metadata
            )]
        
        # Sub-chunking logic
        chunks = []
        current_start = 0
        sub_idx = 0
        while current_start < len(lines):
            end = min(current_start + self.chunk_lines, len(lines))
            chunk_content = "\n".join(lines[current_start:end])
            chunks.append(Chunk(
                content=chunk_content,
                filepath=filepath,
                chunk_index=base_idx + sub_idx,
                line_start=start_line + current_start,
                line_end=start_line + end - 1,
                metadata=metadata
            ))
            current_start += (self.chunk_lines - self.overlap_lines)
            sub_idx += 1
            if current_start >= len(lines):
                break
        return chunks

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        ext = os.path.splitext(filepath)[1]
        lang = self.languages.get(ext)
        
        if not lang:
            # Fallback to line-based chunking if no AST support
            return self._create_chunks_from_text(content, filepath, 1, 0, {})

        self.parser.language = lang
        tree = self.parser.parse(bytes(content, "utf8"))
        root = tree.root_node
        
        chunks = []
        current_idx = 0
        
        # Definition types per language
        def_types = {
            "python": ("function_definition", "class_definition"),
            "go": ("function_declaration", "method_declaration", "type_declaration"),
            "typescript": (
                "function_declaration", "method_definition", "class_declaration", 
                "interface_declaration", "type_alias_declaration", "enum_declaration",
                "arrow_function", "variable_declaration"
            ),
            "yaml": ("block_mapping_pair",),
            "hcl": ("block",)
        }
        
        if ext == ".py":
            lang_name = "python"
        elif ext == ".go":
            lang_name = "go"
        elif ext in (".ts", ".tsx"):
            lang_name = "typescript"
        elif ext in (".yaml", ".yml"):
            lang_name = "yaml"
        elif ext == ".tf":
            lang_name = "hcl"
        else:
            lang_name = "unknown"
            
        target_types = def_types.get(lang_name, ())

        # Keep track of content that isn't inside a definition
        buffer_nodes = []
        
        def flush_buffer(nodes, start_idx):
            if not nodes:
                return [], start_idx
            
            start_line = nodes[0].start_point[0] + 1
            end_line = nodes[-1].end_point[0] + 1
            # Extract text for these nodes
            lines = content.splitlines()
            buffer_text = "\n".join(lines[start_line-1:end_line])
            
            new_chunks = self._create_chunks_from_text(
                buffer_text, filepath, start_line, start_idx, {"type": "general"}
            )
            return new_chunks, start_idx + len(new_chunks)

        for child in root.children:
            if child.type in target_types:
                # Flush buffer first
                if buffer_nodes:
                    buf_chunks, next_idx = flush_buffer(buffer_nodes, current_idx)
                    chunks.extend(buf_chunks)
                    current_idx = next_idx
                    buffer_nodes = []
                
                # Process definition node
                name = self._get_node_name(child)
                start_line = child.start_point[0] + 1
                node_text = child.text.decode("utf8")
                
                metadata = {
                    "type": child.type,
                    "symbols": [name] if name else []
                }
                
                node_chunks = self._create_chunks_from_text(
                    node_text, filepath, start_line, current_idx, metadata
                )
                chunks.extend(node_chunks)
                current_idx += len(node_chunks)
            else:
                buffer_nodes.append(child)
        
        # Final flush
        if buffer_nodes:
            buf_chunks, _ = flush_buffer(buffer_nodes, current_idx)
            chunks.extend(buf_chunks)
            
        return chunks
