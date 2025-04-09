import pytest
from src.logic import AND, OR, XOR, NAND, NOR, XNOR

def test_and_all_true():
    assert AND([True, True, True]) == True

def test_and_one_false():
    assert AND([True, False, True]) == False

def test_and_all_false():
    assert AND([False, False, False]) == False

def test_and_empty_list():
    assert AND([]) == False

def test_and_single_true():
    assert AND([True]) == True

def test_and_single_false():
    assert AND([False]) == False

def test_or_all_true():
    assert OR([True, True, True]) == True

def test_or_one_true():
    assert OR([False, True, False]) == True

def test_or_all_false():
    assert OR([False, False, False]) == False

def test_or_empty_list():
    assert OR([]) == False

def test_or_single_true():
    assert OR([True]) == True

def test_or_single_false():
    assert OR([False]) == False

def test_xor_all_true():
    assert XOR([True, True, True]) == False

def test_xor_one_true():
    assert XOR([False, True, False]) == True

def test_xor_all_false():
    assert XOR([False, False, False]) == False

def test_xor_two_true():
    assert XOR([True, True, False]) == False

def test_xor_empty_list():
    assert XOR([]) == False

def test_xor_single_true():
    assert XOR([True]) == True

def test_xor_single_false():
    assert XOR([False]) == False

def test_nand_all_true():
    assert NAND([True, True, True]) == False

def test_nand_one_false():
    assert NAND([True, False, True]) == True

def test_nand_all_false():
    assert NAND([False, False, False]) == True

def test_nand_empty_list():
    assert NAND([]) == True

def test_nand_single_true():
    assert NAND([True]) == False

def test_nand_single_false():
    assert NAND([False]) == True

def test_nor_all_true():
    assert NOR([True, True, True]) == False

def test_nor_one_true():
    assert NOR([False, True, False]) == False

def test_nor_all_false():
    assert NOR([False, False, False]) == True

def test_nor_empty_list():
    assert NOR([]) == True

def test_nor_single_true():
    assert NOR([True]) == False

def test_nor_single_false():
    assert NOR([False]) == True

def test_xnor_all_true():
    assert XNOR([True, True, True]) == True

def test_xnor_one_true():
    assert XNOR([False, True, False]) == False

def test_xnor_all_false():
    assert XNOR([False, False, False]) == True

def test_xnor_two_true():
    assert XNOR([True, True, False]) == True

def test_xnor_empty_list():
    assert XNOR([]) == True

def test_xnor_single_true():
    assert XNOR([True]) == False

def test_xnor_single_false():
    assert XNOR([False]) == True







