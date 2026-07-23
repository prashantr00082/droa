import re
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

def robust_invoke(llm, prompt_text: str, schema_class):
    """
    Attempts to use native structured output, but falls back to manual prompt injection
    and regex JSON extraction if the open-source proxy model fails to follow strict tool calling.
    """
    # Try native structured output first
    try:
        structured_llm = llm.with_structured_output(schema_class)
        return structured_llm.invoke(prompt_text)
    except Exception as native_e:
        print(f"      [Robust Parser] Native structured output failed: {native_e}")
        print("      [Robust Parser] Falling back to manual JSON extraction...")
        
        parser = PydanticOutputParser(pydantic_object=schema_class)
        instructions = parser.get_format_instructions()
        
        full_prompt = (
            prompt_text + 
            "\n\nCRITICAL: You MUST output ONLY a valid JSON object matching the following schema. "
            "Do not include any conversational text or markdown outside of the JSON block.\n\n" + 
            instructions
        )
        
        response = llm.invoke(full_prompt)
        text = response.content.strip()
        
        # Attempt to extract JSON from markdown code blocks if present
        match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            
        try:
            return schema_class.model_validate_json(text)
        except Exception as e:
            # If it still fails, print the raw output so the user can debug what the LLM did
            print(f"      [Robust Parser] FATAL: Failed to parse JSON even after fallback.")
            print(f"      [Robust Parser] Raw LLM Output:\n{text}")
            raise e
